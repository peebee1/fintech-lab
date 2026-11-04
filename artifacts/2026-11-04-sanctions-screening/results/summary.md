```
book 2400 customers, list 26 entries, 36 true matches, 110 namesakes
review budget 48 cases (2.00% of the book)

policy             reviewed  caught  namesakes  precision  recall     f1   days
exact_name               48      11         36      0.229   0.306  0.262    2.7
name_only                48      11         36      0.229   0.306  0.262   11.5
name_country             48      21         11      0.438   0.583  0.500    3.0
entity_resolution        48      33         11      0.688   0.917  0.786    4.1

queue and ordering at the same budget
policy              queued   days    top   at top  alerted true  ranking loss
exact_name             130    2.7   1.00      130            28            17
name_only              553   11.5   1.00      130            28            17
name_country           144    3.0   1.00       32            21             0
entity_resolution      196    4.1   1.00       30            33             0

recall by class of true match, entity resolution versus name only
class            n    er   name only
exact            7     7           1
alias           14    14           8
year_only        3     3           0
relocated        6     6           0
thin_kyc         3     3           2
kunya            3     0           0

tie break sensitivity: true catches with customer id ascending vs descending
  exact_name                11 vs   12
  name_only                 11 vs   12
  name_country              21 vs   21
  entity_resolution         33 vs   33

entity resolution alerts by rule
  id_exact                     10 alerts   10 true  precision 1.000
  name_close_dob                5 alerts    4 true  precision 0.800
  name_exact_dob               16 alerts   16 true  precision 1.000
  name_no_dob                   3 alerts    3 true  precision 1.000
  name_over_dob_conflict      162 alerts    0 true  precision 0.000
  suppressed weak_name_dob_conflict: 85 pairs
```
