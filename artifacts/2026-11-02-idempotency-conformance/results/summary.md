```
implementation    passed    excess value  excess charges
--------------------------------------------------------
naive            3/11            137.50              11
global_key      10/11              0.00               0
store_after      6/11             87.50               7
error_cached    10/11              0.00               0
reserve         11/11              0.00               0

naive:
  FAIL missing_key           missing_key_accepted, charged_without_key
  FAIL replay_same_body      replay_not_marked, replay_header_missing, replay_body_differs, replay_double_charged
  FAIL replay_different_body conflict_not_refused, conflict_re_executed, conflict_changed_amount
  FAIL overlap_two           overlap_second_executed, overlap_second_charged, overlap_double_charged
  FAIL burst_five            burst_multiple_charges, burst_double_charged
  FAIL crash_after_effect    recovery_not_marked_replay, recovery_returned_other_charge, crash_double_charged
  FAIL in_lease_replay       lease_not_enforced, lease_wrong_error, lease_no_retry_after, lease_replay_double_charged
  FAIL expiry                expired_key_not_refused, expired_wrong_error, expiry_double_charged
global_key:
  FAIL key_scope             cross_account_collision, charge_leaked_to_other_account, scope_charge_count, scope_wrong_total
store_after:
  FAIL overlap_two           overlap_second_executed, overlap_second_charged, overlap_double_charged
  FAIL burst_five            burst_multiple_charges, burst_double_charged
  FAIL crash_after_effect    recovery_not_marked_replay, recovery_returned_other_charge, crash_double_charged
  FAIL in_lease_replay       lease_not_enforced, lease_wrong_error, lease_no_retry_after, lease_replay_double_charged
  FAIL expiry                expired_key_not_refused, expired_wrong_error
error_cached:
  FAIL error_then_retry      error_cached_as_final, retry_not_executed, error_retry_charge_count
```
