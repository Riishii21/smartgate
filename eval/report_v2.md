# Evaluation report

Mode: classification + gate | cases: 65 | wall clock: 181.7s | mean latency: 2.79s

## Headline

| Metric | Value |
| --- | --- |
| Type accuracy (unambiguous, n=60) | **88.3%** |
| Urgency exact | 83.3% |
| Urgency within one level | 100.0% |
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
| billing_dispute | 17 | 0 | 0 | 0 |
| general_enquiry | 0 | 16 | 2 | 0 |
| service_request | 0 | 0 | 15 | 0 |
| complaint | 2 | 0 | 3 | 10 |

## Per-type accuracy

- `billing_dispute` 100.0%  ########################  (15/15)
- `general_enquiry`  86.7%  #####################...  (13/15)
- `service_request` 100.0%  ########################  (15/15)
- `complaint`  66.7%  ################........  (10/15)

## Misclassifications (7)

| id | expected | got | conf | held | note |
| --- | --- | --- | --- | --- | --- |
| ge13 | general_enquiry | service_request | 0.95 | no | - |
| ge15 | general_enquiry | service_request | 0.95 | no | borderline service request |
| cp02 | complaint | service_request | 0.90 | yes | bereavement |
| cp06 | complaint | billing_dispute | 0.90 | no | - |
| cp10 | complaint | service_request | 0.80 | no | - |
| cp12 | complaint | billing_dispute | 0.90 | no | - |
| cp15 | complaint | service_request | 0.90 | yes | bereavement |
