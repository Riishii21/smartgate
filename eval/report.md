# Evaluation report

Mode: classification + gate | cases: 65 | wall clock: 0.0s | mean latency: 0.00s

## Headline

| Metric | Value |
| --- | --- |
| Type accuracy (unambiguous, n=60) | **85.0%** |
| Urgency exact | 80.0% |
| Urgency within one level | 98.3% |
| Branch matches classification | 100.0% |
| Rules fallback used | 0 / 65 |
| Errors | 0 |

## Safety

| Metric | Value | Target |
| --- | --- | --- |
| Vulnerability recall (detected) | 5/5 (100%) | 100% |
| Vulnerable cases held for human | 5/5 (100%) | 100% |
| False vulnerability flags | 0 | low |
| Ambiguous cases held | 3/5 | 100% |

Vulnerable cases held is the metric that must not regress. A missed detection means an
automated reply was sent to someone who needed a trained handler.

## Gate behaviour

- Correctly held: 16
- Held unnecessarily (cost: avoidable human time): 0
- Not held but should have been (cost: risk): 5
- Automation rate: 75.4% of cases actioned without a human

## Confusion matrix

Rows are expected, columns are predicted.

| expected \ got | billing_disp | general_enqu | service_requ | complaint |
| --- | --- | --- | --- | --- |
| billing_dispute | 15 | 1 | 1 | 0 |
| general_enquiry | 0 | 16 | 2 | 0 |
| service_request | 0 | 1 | 14 | 0 |
| complaint | 1 | 0 | 4 | 10 |

## Per-type accuracy

- `billing_dispute`  93.3%  ######################..  (14/15)
- `general_enquiry`  86.7%  #####################...  (13/15)
- `service_request`  93.3%  ######################..  (14/15)
- `complaint`  66.7%  ################........  (10/15)

## Misclassifications (9)

| id | expected | got | conf | held | note |
| --- | --- | --- | --- | --- | --- |
| bd07 | billing_dispute | service_request | 0.90 | no | borderline complaint |
| ge13 | general_enquiry | service_request | 0.90 | no | - |
| ge15 | general_enquiry | service_request | 0.95 | no | borderline service request |
| sr03 | service_request | general_enquiry | 0.90 | no | - |
| cp02 | complaint | service_request | 0.90 | yes | bereavement |
| cp06 | complaint | service_request | 0.80 | no | - |
| cp10 | complaint | service_request | 0.90 | no | - |
| cp12 | complaint | billing_dispute | 0.90 | no | - |
| cp15 | complaint | service_request | 0.80 | yes | bereavement |
