# PRG4SSL-MNAR

## Results (e.g. seed=1)

| Dateset | Labels | N0 |gamma|Acc|Setting|Method|Weight|
| :-----:| :----: | :----: |:----: |:----: |:----: |:----: |:----: |
|CIFAR-10 | 40 | - |-|94.05 |Conventional settings|PRG||
| | 250 | - |- |94.36 |||
| | 4000 | - |- |95.48 |||
| | 40 | - |-|93.79 |Conventional settings|PRG^Last|
| | 250 | - |- |94.76 |||
| | 4000 | - |- |95.75 |||
| | - | - |20 |94.04 |CADR's protocol|PRG|
| | - | - |50 |93.78 |||
| | - | - |100 |94.51 |||
| | - | - |20 |94.74 |CADR's protocol|PRG^Last|
| | - | - |50 |94.74 |||
| | - | - |100 |94.75 |||
| | 40 | 10 |- |93.81 |Ours protocol|PRG|[here][cf10-o-4010-p]|
| | 40 | 20 |- |93.39 |||
| | 40 | 10 |2 |90.25 |||
| | 40 | 10 |5 |82.84 |||
| | 100 | 40 |5 |79.58 |||
| | 100 | 40 |10 |78.61 |||
| | 250 | 100 |- |93.76 |||
| | 250 | 200 |- |91.65 |||
| | 40 | 10 |- |91.56 |Ours protocol|PRG^Last|
| | 40 | 20 |- |80.31 |||
| | 250 | 100 |- |91.36 |||
| | 250 | 200 |- |62.16 |||
|  | DARP | 100 |1 |94.41 |DARP's protocol|PRG|
|  | DARP | 100 |50 |78.28 |||
|  | DARP | 100 |150 |75.21 |||
|  | DARP (reversed) | 100 |100 |80.86 |||
|CIFAR-100  | 400 | - |- |48.67 |Conventional settings|PRG|
|  | 2500 | - |- |69.81|||
|  | 10000 | - |- |76.91 |||
|  | 400 | - |- |48.66 |Conventional settings|PRG^Last|
|  | 2500 | - |- |70.03|||
|  | 10000 | - |- |76.93 |||
|  | - | - |50 |58.57 |CADR's protocol|PRG|[here][cf100-c-50-p]|
|  | - | - |100 |62.28 |||
|  | - | - |200 |59.33 |||[here][cf100-c-200-p]|
|  | - | - |50 |60.32 |CADR's protocol|PRG^Last|
|  | - | - |100 |62.13 |||[here][cf100-c-100-l]|
|  | - | - |200 |58.70 |||
|  | 2500 | 100 |- |57.56 |Ours protocol|PRG|[here][cf100-o-2500100-p]|
|  | 2500 | 200 |- |51.21 |||
|  | 2500 | 100 |- |59.40 |Ours protocol|PRG^Last|
|  | 2500 | 200 |- |42.09 |||
|mini-ImageNet | 1000| -|- |45.74 |Conventional settings|PRG|
| | 1000| -|- |48.63 |Conventional settings|PRG^Last|[here][mini-con-1000-l]|
| | -| -|50 |43.74 |CADR's protocol|PRG|
| | -| - |100 |43.74 |||
| | -| -|50 |42.22 |CADR's protocol|PRG^Last|
| | -| - |100 |43.74 |||
| | 1000| 40 |- |40.75 |Ours protocol|||
| | 1000| 80 |- |35.86|||

[cf10-o-4010-p]: https://1drv.ms/u/s!Ao848hI985sshjh2bBYISxTEZ7XV?e=eRKPSo
[cf100-o-2500100-p]: https://1drv.ms/u/s!Ao848hI985sshjqrNL0LjoopBC1z?e=pXsaa3
[cf100-c-50-p]: https://1drv.ms/u/s!Ao848hI985sshjyMzIqjED8QnAFz?e=cW0Gue
[cf100-c-200-p]: https://1drv.ms/u/s!Ao848hI985sshj4rvVK_PKMggLgp?e=RppGev
[cf100-c-100-l]: https://1drv.ms/u/s!Ao848hI985sshkDQSOXOORRu5r14?e=cWO7pp
[mini-con-1000-l]: https://1drv.ms/u/s!Ao848hI985sshkJcenD9uLqNw3h2?e=gF7gZa
[mini-c-50-p]: https://1drv.ms/u/s!Ao848hI985sshkRgrVU8raF2CHEe?e=3rnf47
