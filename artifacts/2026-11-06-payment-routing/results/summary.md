```
book 50000 synthetic transactions, digest eb0f27f3d9be0528
margin 15.0% of ticket, ops 2c per attempt, retry depth 1

policy           att/txn   auth%  fee bps  net $/1000  vs cheapest
cheapest            1.10   88.9%    124.4   38,271.18        +0.00
static_rules        1.05   94.3%    150.7   39,824.57    +1,553.39
epsilon_greedy      1.07   92.3%    151.6   39,441.33    +1,170.15
thompson            1.06   93.9%    150.2   39,778.31    +1,507.13
thompson_window     1.07   92.9%    138.7   39,190.48      +919.30
oracle              1.05   94.3%    151.3   39,801.84    +1,530.66

where the fee only choice is wrong, single attempt expectation
segment                             n  ticket  fee arm    best   gap $/txn
debit/cross_border/large         1841     848    alpha charlie       25.00
credit/cross_border/large        1496     857    alpha charlie       10.19
debit/domestic/large             6462     849    alpha   bravo        6.80
debit/cross_border/mid           2719     117    alpha charlie        3.17
credit/cross_border/mid          2169     116    alpha charlie        1.13
debit/domestic/mid               9728     114    alpha   bravo        0.95
debit/cross_border/micro         1504      17    alpha charlie        0.49
credit/domestic/micro            4362      17  charlie   alpha        0.28
debit/domestic/micro             5346      17  charlie   bravo        0.26
credit/cross_border/micro        1253      17  charlie charlie        0.00
credit/domestic/large            5305     852    alpha   alpha        0.00
credit/domestic/mid              7815     115    alpha   alpha        0.00

retry depth sweep
 depth  cheap auth%  oracle auth%  cheap fee bps  gap $/1000
     0        83.7%         91.7%          122.5    2,688.78
     1        88.9%         94.3%          124.4    1,530.66
     2        90.5%         95.0%          125.6    1,150.78

margin assumption sweep
  margin%   cheapest $/1000  oracle $/1000   gap %
       10         24,352.42      25,062.60     2.9
       15         38,271.18      39,801.84     4.0
       22         57,757.61      60,471.32     4.7

thompson learning curve, net $ per 1000 by block, against full knowledge
block  1  thompson 38,550.65  oracle 38,820.41
block  2  thompson 40,514.89  oracle 40,336.14
block  3  thompson 39,883.18  oracle 39,966.03
block  4  thompson 39,875.25  oracle 40,028.34
block  5  thompson 39,960.90  oracle 40,056.80
block  6  thompson 40,218.46  oracle 40,380.38
block  7  thompson 40,777.04  oracle 40,682.32
block  8  thompson 38,576.80  oracle 38,585.43
block  9  thompson 40,545.96  oracle 40,404.91
block 10  thompson 38,879.99  oracle 38,757.66

segments 12, fee only arm is not best in 9, is worst in 7

regime shift at transaction 25000: bravo loses 0.90 logit on channel:debit
policy            net before  net after    change  auth after
cheapest           38,066.60  38,341.04   +274.44       88.5%
static_rules       39,789.14  38,618.72 -1,170.42       91.2%
thompson           39,756.97  38,481.39 -1,275.58       90.4%
thompson_window    39,030.95  38,987.56    -43.39       90.3%
oracle             39,841.54  38,969.57   -871.97       91.8%

net $ per 1000 by block after the shift
 block     static   thompson    window    oracle
     6  38,975.99  38,794.31 40,082.95 40,061.90
     7  39,454.01  39,302.32 39,597.76 39,418.84
     8  37,599.16  37,557.64 37,722.88 37,871.40
     9  39,494.34  39,326.37 39,585.31 39,557.27
    10  37,570.10  37,426.31 37,948.91 37,938.44
```
