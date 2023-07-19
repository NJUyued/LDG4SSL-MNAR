# import needed library
import os
import logging
import random
import warnings

import numpy as np
import torch
import torch.nn as nn
import torch.nn.parallel
import torch.backends.cudnn as cudnn
import torch.distributed as dist
import torch.multiprocessing as mp

from utils import net_builder, get_logger, count_parameters
from train_utils import TBLog, get_SGD, get_cosine_schedule_with_warmup, get_nodecay_schedule
from models.prg.prg import PRG
from datasets.ssl_dataset import SSL_Dataset
from datasets.data_utils import get_data_loader

# os.environ['CUDA_VISIBLE_DEVICES'] = '0' 
def main(args):
    '''
    For (Distributed)DataParallelism,
    main(args) spawn each process (main_worker) to each GPU.
    '''

    save_path = os.path.join(args.save_dir, args.save_name)
    if os.path.exists(save_path) and not args.overwrite:
        raise Exception('already existing model: {}'.format(save_path))
    if args.resume:
        if args.load_path is None:
            raise Exception('Resume of training requires --load_path in the args')
        if os.path.abspath(save_path) == os.path.abspath(args.load_path) and not args.overwrite:
            raise Exception('Saving & Loading pathes are same. \
                            If you want over-write, give --overwrite in the argument.')
        
    if args.seed is not None:
        warnings.warn('You have chosen to seed training. '
                      'This will turn on the CUDNN deterministic setting, '
                      'which can slow down your training considerably! '
                      'You may see unexpected behavior when restarting '
                      'from checkpoints.')
        
    if args.gpu is not None:
        warnings.warn('You have chosen a specific GPU. This will completely '
                      'disable data parallelism.')
    
    if args.dist_url == "env://" and args.world_size == -1:
        args.world_size = int(os.environ["WORLD_SIZE"])
    
    #distributed: true if manually selected or if world_size > 1
    args.distributed = args.world_size > 1 or args.multiprocessing_distributed 
    ngpus_per_node = torch.cuda.device_count() # number of gpus of each node
    
    #divide the batch_size according to the number of nodes
    args.batch_size = int(args.batch_size / args.world_size)
    
    if args.multiprocessing_distributed:
        # now, args.world_size means num of total processes in all nodes
        args.world_size = ngpus_per_node * args.world_size 
        
        #args=(,) means the arguments of main_worker
        mp.spawn(main_worker, nprocs=ngpus_per_node, args=(ngpus_per_node, args)) 
    else:
        main_worker(args.gpu, ngpus_per_node, args)
    

def main_worker(gpu, ngpus_per_node, args):
    '''
    main_worker is conducted on each GPU.
    '''
    
    global best_acc1
    args.gpu = gpu
    
    # random seed has to be set for the syncronization of labeled data sampling in each process.
    assert args.seed is not None
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    cudnn.deterministic = True
    

    # SET UP FOR DISTRIBUTED TRAINING
    if args.distributed:
        if args.dist_url == "env://" and args.rank == -1:
            args.rank = int(os.environ["RANK"])
        if args.multiprocessing_distributed:
            args.rank = args.rank * ngpus_per_node + gpu # compute global rank
        
        # set distributed group:
        dist.init_process_group(backend=args.dist_backend, init_method=args.dist_url,
                                world_size=args.world_size, rank=args.rank)
    
    
    #SET save_path and logger
    save_path = os.path.join(args.save_dir, args.save_name)
    logger_level = "WARNING"
    tb_log = None
    if args.rank % ngpus_per_node == 0:
        tb_log = TBLog(save_path, 'tensorboard')
        logger_level = "INFO"
    
    logger = get_logger(args.save_name, save_path, logger_level)
    logger.warning(f"USE GPU: {args.gpu} for training")
    
    
    args.bn_momentum = 1.0 - args.ema_m
    _net_builder = net_builder(args.net, 
                               {'depth': args.depth, 
                                'widen_factor': args.widen_factor,
                                'leaky_slope': args.leaky_slope,
                                'bn_momentum': args.bn_momentum,
                                'dropRate': args.dropout})
    
    model = PRG(_net_builder,
                     args.num_classes,
                     args.ema_m,
                     args.T,
                     args.p_cutoff,
                     args.ulb_loss_ratio,
                     args.hard_label,
                     num_eval_iter=args.num_eval_iter,
                     tb_log=tb_log,
                     logger=logger)

    logger.info(f'Number of Trainable Params: {count_parameters(model.train_model)}')
        

    # SET Optimizer & LR Scheduler
    ## construct SGD and cosine lr scheduler
    optimizer = get_SGD(model.train_model, 'SGD', args.lr, args.momentum, args.weight_decay)
    if args.lr_decay=='cos':
        scheduler = get_cosine_schedule_with_warmup(optimizer,
                                                args.num_train_iter,
                                                num_warmup_steps=args.num_train_iter*0)
    else:
        scheduler = get_nodecay_schedule(optimizer)
    ## set SGD and cosine lr on PRG 
    model.set_optimizer(optimizer, scheduler)
    
    
    # SET Devices for (Distributed) DataParallel
    if not torch.cuda.is_available():
        raise Exception('ONLY GPU TRAINING IS SUPPORTED')
    elif args.distributed:
        if args.gpu is not None:
            torch.cuda.set_device(args.gpu)            
            '''
            batch_size: batch_size per node -> batch_size per gpu
            workers: workers per node -> workers per gpu
            '''
            args.batch_size = int(args.batch_size / ngpus_per_node)
            model.train_model.cuda(args.gpu)
            model.train_model = torch.nn.parallel.DistributedDataParallel(model.train_model,
                                                                          device_ids=[args.gpu])
            model.eval_model.cuda(args.gpu)
            
        else:
            # if arg.gpu is None, DDP will divide and allocate batch_size
            # to all available GPUs if device_ids are not set.
            model.cuda()
            model = torch.nn.parallel.DistributedDataParallel(model)
            
    elif args.gpu is not None:

        torch.cuda.set_device(args.gpu)
        model.train_model = model.train_model.cuda(args.gpu)
        model.eval_model = model.eval_model.cuda(args.gpu)
        # model.train_model = torch.nn.DataParallel(model.train_model).cuda()
        # model.eval_model = torch.nn.DataParallel(model.eval_model).cuda()
        
        
    else:
        model.train_model = torch.nn.DataParallel(model.train_model).cuda()
        model.eval_model = torch.nn.DataParallel(model.eval_model).cuda()
    
    logger.info(f"model_arch: {model}")
    logger.info(f"Arguments: {args}")
    
    cudnn.benchmark = True

    # Construct Dataset & DataLoader
    loader_dict = {}
    if args.dataset=='miniimage':
        from datasets_mini.miniimage import get_train_loader, get_val_loader
        if args.mismatch == 'bda' and args.n0!=0 and args.gamma==0:
            flag_mismatch = True
        elif (args.mismatch == 'cadr' and args.n0==0 and args.gamma!=0) or (args.mismatch == 'none' and args.gamma==0):
            flag_mismatch = False
        data_para_dict = dict(
            L=args.num_labels, 
            num_workers=args.num_workers, 
            root=args.data_dir, 
            flag_mismatch=flag_mismatch,
            n0=args.n0,
            gamma=args.gamma
        )
        save_path = os.path.join(args.save_dir, args.save_name)
        dltrain_x, dltrain_u, dltrain_u_eval, pre_class_dist = get_train_loader(save_path, args.dataset, args.batch_size, args.uratio, args.num_train_iter, **data_para_dict)
        dlval = get_val_loader(dataset=args.dataset, batch_size=args.eval_batch_size, num_workers=args.num_workers, root=args.data_dir)
        loader_dict['train_lb'] = dltrain_x
        loader_dict['train_ulb'] = dltrain_u
        loader_dict['eval'] = dlval
        loader_dict['eval_ulb'] = dltrain_u_eval
    else:
        train_dset = SSL_Dataset(name=args.dataset, train=True, 
                                num_classes=args.num_classes, data_dir=args.data_dir,  
                                mismatch=args.mismatch, n0=args.n0, gamma=args.gamma)
        if args.dataset=='stl10':
            lb_dset, ulb_dset, eval_ulb_dset = train_dset.get_ssl_dset(args.num_labels, os.path.join(args.save_dir, args.save_name))
        else:
            lb_dset, ulb_dset = train_dset.get_ssl_dset(args.num_labels, os.path.join(args.save_dir, args.save_name))
        
        _eval_dset = SSL_Dataset(name=args.dataset, train=False, 
                                num_classes=args.num_classes, data_dir=args.data_dir)
        eval_dset = _eval_dset.get_dset()
        
        if args.dataset=='stl10':
            dset_dict = {'train_lb': lb_dset, 'train_ulb': ulb_dset, 'eval': eval_dset, 'eval_ulb_stl10':eval_ulb_dset}
        else:
            dset_dict = {'train_lb': lb_dset, 'train_ulb': ulb_dset, 'eval': eval_dset}
        
        
        loader_dict['train_lb'] = get_data_loader(dset_dict['train_lb'],
                                                args.batch_size,
                                                data_sampler = args.train_sampler,
                                                num_iters=args.num_train_iter,
                                                num_workers=args.num_workers, 
                                                distributed=args.distributed)

        loader_dict['full_train_lb'] = get_data_loader(dset_dict['train_ulb'],
                                                args.batch_size,
                                                data_sampler = args.train_sampler,
                                                num_iters=args.num_train_iter,
                                                num_workers=args.num_workers, 
                                                distributed=args.distributed)
        
        loader_dict['train_ulb'] = get_data_loader(dset_dict['train_ulb'],
                                                args.batch_size*args.uratio,
                                                data_sampler = args.train_sampler,
                                                num_iters=args.num_train_iter,
                                                num_workers=4*args.num_workers,
                                                distributed=args.distributed)
        
        loader_dict['eval'] = get_data_loader(dset_dict['eval'],
                                            args.eval_batch_size, 
                                            num_workers=args.num_workers)
        
        if args.dataset=='stl10':
            loader_dict['eval_ulb'] = get_data_loader(dset_dict['eval_ulb_stl10'],
                                                    args.eval_batch_size,                                                                              
                                                    num_workers=args.num_workers)
        else:
            loader_dict['eval_ulb'] = get_data_loader(dset_dict['train_ulb'],
                                                    args.eval_batch_size,                                                                              
                                                    num_workers=args.num_workers)
    
    ## set DataLoader on PRG
    model.set_data_loader(loader_dict)
    
    #If args.resume, load checkpoints from args.load_path
    if args.resume:
        model.load_model(args.load_path)
    
    # START TRAINING of PRG
    trainer = model.train
    for epoch in range(args.epoch):
        trainer(args, logger=logger)
        
    if not args.multiprocessing_distributed or \
                (args.multiprocessing_distributed and args.rank % ngpus_per_node == 0):
        model.save_model('latest_model.pth', save_path)
        
    logging.warning(f"GPU {args.rank} training is FINISHED")
    

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='')

    '''
    Saving & loading of the model.
    '''
    parser.add_argument('--save_dir', type=str, default='./saved_models')
    parser.add_argument('--save_name', type=str, default='fixmatch')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--load_path', type=str, default=None)
    parser.add_argument('--overwrite', action='store_true')
    
    '''
    Training Configuration of PRG
    '''
    parser.add_argument('--Nb', type=int, default=128,
                        help='number of tracked bathches')
    parser.add_argument('--alpha', type=int, default=1,
                        help='class invariance coefficient')
    parser.add_argument('--last', action='store_true',
                        help='choose model from {PRG,PRG^last}')
    parser.add_argument('--epoch', type=int, default=1)
    parser.add_argument('--num_train_iter', type=int, default=2**20, 
                        help='total number of training iterations')
    parser.add_argument('--num_eval_iter', type=int, default=10000,
                        help='evaluation frequency')
    parser.add_argument('--num_labels', type=int, default=4000)
    parser.add_argument('--batch_size', type=int, default=64,
                        help='total number of batch size of labeled data')
    parser.add_argument('--uratio', type=int, default=7,
                        help='the ratio of unlabeled data to labeld data in each mini-batch')
    parser.add_argument('--eval_batch_size', type=int, default=1024,
                        help='batch size of evaluation data loader (it does not affect the accuracy)')
    
    parser.add_argument('--hard_label', type=bool, default=True)
    parser.add_argument('--T', type=float, default=1)
    parser.add_argument('--p_cutoff', type=float, default=0.95)
    parser.add_argument('--ema_m', type=float, default=0.999, help='ema momentum for eval_model')
    parser.add_argument('--ulb_loss_ratio', type=float, default=1.0)
    
    '''
    Optimizer configurations
    '''
    parser.add_argument('--lr', type=float, default=0.03)
    parser.add_argument('--momentum', type=float, default=0.9)
    parser.add_argument('--weight_decay', type=float, default=5e-4)
    parser.add_argument('--amp', action='store_true', help='use mixed precision training or not')
    parser.add_argument('--lr_decay', type=str, default='cos', help='cos->cosine decay,none->no decay')

    '''
    Backbone Net Configurations
    '''
    parser.add_argument('--net', type=str, default='wrn', 
            help='use {wrn,resnet18,preresnet,cnn13} for {Wide ResNet,ResNet-18,PreAct ResNet,CNN-13}')
    parser.add_argument('--depth', type=int, default=28)
    parser.add_argument('--widen_factor', type=int, default=2)
    parser.add_argument('--leaky_slope', type=float, default=0.1)
    parser.add_argument('--dropout', type=float, default=0.0)
    
    '''
    Data Configurations
    '''
    
    parser.add_argument('--data_dir', type=str, default='data')
    parser.add_argument('--dataset', type=str, default='cifar10')
    parser.add_argument('--train_sampler', type=str, default='RandomSampler')
    parser.add_argument('--num_classes', type=int, default=10)
    parser.add_argument('--num_workers', type=int, default=8)
    parser.add_argument('--mismatch', type=str, default='none', choices=['none','prg','cadr','darp','darp_reversed'], help='type of MNAR scenario')
    parser.add_argument('--n0', type=int, default=0, help='imbalanced ratio for labeled data')
    parser.add_argument('--gamma', type=int, default=0, help='imbalanced ratio for unlabeled data')
    
    '''
    multi-GPUs & Distrbitued Training
    '''
    
    ## args for distributed training (from https://github.com/pytorch/examples/blob/master/imagenet/main.py)
    parser.add_argument('--world-size', default=-1, type=int,
                        help='number of nodes for distributed training')
    parser.add_argument('--rank', default=-1, type=int,
                        help='**node rank** for distributed training')
    parser.add_argument('--dist-url', default='tcp://127.0.0.1:10002', type=str,
                        help='url used to set up distributed training')
    parser.add_argument('--dist-backend', default='nccl', type=str,
                        help='distributed backend')
    parser.add_argument('--seed', default=1, type=int,
                        help='seed for initializing training. ')
    parser.add_argument('--gpu', default=None, type=int,
                        help='GPU id to use.')
    parser.add_argument('--multiprocessing-distributed', action='store_true',
                        help='Use multi-processing distributed training to launch '
                             'N processes per node, which has N GPUs. This is the '
                             'fastest way to use PyTorch for either single node or '
                             'multi node data parallel training')
     
    args = parser.parse_args()
    
    main(args)
