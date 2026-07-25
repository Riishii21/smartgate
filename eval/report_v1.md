# Evaluation report

Mode: classification + gate | cases: 65 | wall clock: 120.0s | mean latency: 1.85s

## Headline

| Metric | Value |
| --- | --- |
| Type accuracy (unambiguous, n=60) | **88.3%** |
| Urgency exact | 30.0% |
| Urgency within one level | 81.7% |
| Branch matches classification | 100.0% |
| Rules fallback used | 1 / 65 |
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

- Correctly held: 8
- Held unnecessarily (cost: avoidable human time): 0
- Not held but should have been (cost: risk): 13
- Automation rate: 87.7% of cases actioned without a human

## Confusion matrix

Rows are expected, columns are predicted.

| expected \ got | billing_disp | general_enqu | service_requ | complaint |
| --- | --- | --- | --- | --- |
| billing_dispute | 17 | 0 | 0 | 0 |
| general_enquiry | 0 | 16 | 2 | 0 |
| service_request | 0 | 0 | 15 | 0 |
| complaint | 2 | 1 | 2 | 10 |

## Per-type accuracy

- `billing_dispute` 100.0%  ########################  (15/15)
- `general_enquiry`  86.7%  #####################...  (13/15)
- `service_request` 100.0%  ########################  (15/15)
- `complaint`  66.7%  ################........  (10/15)

## Misclassifications (7)

| id | expected | got | conf | held | note |
| --- | --- | --- | --- | --- | --- |
| ge13 | general_enquiry | service_request | 0.90 | no | - |
| ge15 | general_enquiry | service_request | 0.90 | no | borderline service request |
| cp02 | complaint | general_enquiry | 0.20 | yes | bereavement |
| cp06 | complaint | billing_dispute | 0.80 | no | - |
| cp10 | complaint | service_request | 0.90 | no | - |
| cp12 | complaint | billing_dispute | 0.90 | no | - |
| cp15 | complaint | service_request | 0.90 | yes | bereavement |
