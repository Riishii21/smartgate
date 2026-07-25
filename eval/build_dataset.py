"""Generate the labelled evaluation dataset.

Cases are hand-written rather than model-generated so the ground truth is
independent of the system being measured. Roughly a fifth are deliberately hard:
tone that contradicts intent, mixed requests, and vulnerability disclosures.
"""
import json
import pathlib

# (id, subject, text, type, urgency, vulnerable, note)
CASES = [
    # ---------------- billing disputes (15) ----------------
    ("bd01", "Duplicate charge", "I've been charged twice for the same £42.50 order at Halewood Books on 3 July. Please refund the second one.", "billing_dispute", "high", False, ""),
    ("bd02", "Payment I didn't make", "There is a payment of £212.40 to Vertex Media on my statement. I have never heard of this company and did not authorise it.", "billing_dispute", "high", False, ""),
    ("bd03", "ABSOLUTELY FURIOUS", "I am beyond angry. A charge of £89 has appeared from some company I've never dealt with. This is unacceptable and I want it dealt with TODAY.", "billing_dispute", "high", False, "angry tone, dispute intent"),
    ("bd04", "Wrong amount taken", "The restaurant bill was £64 but £640 has come out of my account. Obviously a decimal error somewhere.", "billing_dispute", "high", False, ""),
    ("bd05", "Subscription still charging", "I cancelled my gym membership in April but they have taken another £39.99 this month. Can you stop it and refund me?", "billing_dispute", "high", False, ""),
    ("bd06", "Hotel charged me twice", "Booked one room, charged for two. The hotel says it's your side. £310 in total.", "billing_dispute", "high", False, ""),
    ("bd07", "Refund never arrived", "The retailer confirmed a refund of £128 three weeks ago and it still hasn't reached my card.", "billing_dispute", "high", False, "borderline complaint"),
    ("bd08", "Query on a transaction", "Could you tell me what the £17.99 to 'PP*DIGITAL' on 9 July is? I don't recognise it and I'd like it reversed if it isn't mine.", "billing_dispute", "high", False, "enquiry phrasing, dispute intent"),
    ("bd09", "Contactless used after loss", "My card was in my coat which went missing on Saturday. There are four contactless payments after that I didn't make.", "billing_dispute", "critical", False, "fraud, higher urgency"),
    ("bd10", "Free trial charged", "I signed up for a free trial and have been billed £59 without warning. I want this reversed.", "billing_dispute", "high", False, ""),
    ("bd11", "Currency conversion wrong", "I paid 40 euros but was charged £48. The rate that day was nowhere near that.", "billing_dispute", "high", False, "fee query vs dispute"),
    ("bd12", "Two charges same second", "Two identical charges of £23.10 from the same merchant, timestamped one second apart.", "billing_dispute", "high", False, ""),
    ("bd13", "Cancelled order still charged", "The order was cancelled before dispatch but the money has still left my account.", "billing_dispute", "high", False, ""),
    ("bd14", "Disputed charge - polite", "Good morning. I'm sorry to trouble you, but there's a charge for £75 I don't believe is mine. Could you look into it when you have a moment? Many thanks.", "billing_dispute", "high", False, "polite tone, dispute intent"),
    ("bd15", "ATM didn't dispense", "The machine debited £200 but no cash came out. This was at the Kingsway branch on Tuesday.", "billing_dispute", "high", False, ""),

    # ---------------- general enquiries (15) ----------------
    ("ge01", "Balance transfer", "How long does a balance transfer normally take, and should I keep paying the old card meanwhile?", "general_enquiry", "low", False, ""),
    ("ge02", "Interest question", "If I clear my balance in full each month, do I pay any interest on purchases?", "general_enquiry", "low", False, ""),
    ("ge03", "Using card abroad", "I'm travelling to Spain next month. What fees apply when I use the card there?", "general_enquiry", "low", False, ""),
    ("ge04", "Statement access", "Where do I find my old statements in online banking? I need one from last year.", "general_enquiry", "low", False, ""),
    ("ge05", "Credit limit criteria", "What do you look at when deciding whether to increase someone's credit limit?", "general_enquiry", "low", False, ""),
    ("ge06", "Direct debit timing", "How long does it take for a new direct debit to become active?", "general_enquiry", "low", False, ""),
    ("ge07", "Dispute window", "Just out of interest, how long do I have to dispute a transaction after it happens?", "general_enquiry", "low", False, "mentions dispute, no actual dispute"),
    ("ge08", "Card delivery time", "If a replacement card is ordered, roughly how long does it take to arrive?", "general_enquiry", "low", False, ""),
    ("ge09", "Annoyed but asking", "Honestly your website is hopeless. Can you just tell me what the current APR is?", "general_enquiry", "low", False, "irritated tone, enquiry intent"),
    ("ge10", "Closing process", "What's involved in closing an account? Not asking you to close it yet, just want to know.", "general_enquiry", "low", False, "service-request phrasing, enquiry intent"),
    ("ge11", "Cash withdrawal fees", "Are there charges for withdrawing cash on a credit card at a UK machine?", "general_enquiry", "low", False, ""),
    ("ge12", "Minimum payment", "How is the minimum payment on my statement calculated?", "general_enquiry", "low", False, ""),
    ("ge13", "Additional cardholder", "Can I add my daughter as an additional cardholder, and what's the age limit?", "general_enquiry", "low", False, ""),
    ("ge14", "Fraud protection", "What protection do I have if someone uses my card fraudulently?", "general_enquiry", "low", False, ""),
    ("ge15", "Paperless billing", "Is there a way to stop receiving paper statements in the post?", "general_enquiry", "low", False, "borderline service request"),

    # ---------------- service requests (15) ----------------
    ("sr01", "Change of address", "I've moved to 14 Mill Lane, Leeds LS6 2AB. Please update the address on the card ending 6467.", "service_request", "medium", False, ""),
    ("sr02", "Lost card", "I've lost my card somewhere between the office and home. Please block it and send a replacement.", "service_request", "high", False, "urgency higher than typical"),
    ("sr03", "Statement copy", "Could you post me copies of my statements for January to March please?", "service_request", "medium", False, ""),
    ("sr04", "Limit increase", "I'd like to request an increase to my credit limit, from £3,000 to £5,000.", "service_request", "medium", False, ""),
    ("sr05", "Name change", "I got married last month and need the name on my account updated to Sarah Okonkwo.", "service_request", "medium", False, ""),
    ("sr06", "Cancel direct debit", "Please cancel the direct debit to Anytime Fitness on my account.", "service_request", "medium", False, ""),
    ("sr07", "Damaged card", "The chip on my card has stopped working. Can you send out a new one?", "service_request", "medium", False, ""),
    ("sr08", "Close account", "I'd like to close my account. The balance is cleared as of yesterday.", "service_request", "medium", False, ""),
    ("sr09", "Address change no detail", "I have moved house. Please update my address on the card ending 6467.", "service_request", "medium", False, "missing required detail"),
    ("sr10", "Travel notification", "I'll be in Japan from the 3rd to the 20th. Please note it so my card isn't blocked.", "service_request", "medium", False, ""),
    ("sr11", "PIN reminder", "I've forgotten my PIN. How do I get a reminder sent out?", "service_request", "medium", False, "phrased as enquiry, action needed"),
    ("sr12", "Phone number update", "New mobile number for the account please, the old one is no longer in use.", "service_request", "medium", False, ""),
    ("sr13", "Paperless switch", "Please switch me to paperless statements with immediate effect.", "service_request", "medium", False, ""),
    ("sr14", "Remove cardholder", "I'd like to remove my ex-partner as an additional cardholder on the account.", "service_request", "medium", False, ""),
    ("sr15", "Payment date change", "Can my monthly payment date be moved from the 1st to the 15th?", "service_request", "medium", False, ""),

    # ---------------- complaints (15) ----------------
    ("cp01", "Third time writing", "This is the third time I have written. Nobody has actioned my request and I have now had a late payment letter. The service has been appalling.", "complaint", "high", False, ""),
    ("cp02", "Bereavement ignored", "My husband passed away in May and I asked you in June to move the account into my name. Nothing has happened and I am struggling to keep on top of this.", "complaint", "critical", True, "bereavement"),
    ("cp03", "Rude on the phone", "The adviser I spoke to yesterday was dismissive and talked over me repeatedly. I want this looked into.", "complaint", "high", False, ""),
    ("cp04", "Hardship ignored", "I lost my job in April and told you I couldn't afford the payments. You've added charges anyway and I genuinely cannot cope with this.", "complaint", "critical", True, "financial hardship + distress"),
    ("cp05", "Promised callback", "I was promised a callback within 24 hours. That was eight days ago. Nothing.", "complaint", "high", False, ""),
    ("cp06", "Wrongly declined", "My card was declined at a hospital car park even though I had plenty of available credit. Deeply embarrassing and I want an explanation.", "complaint", "high", False, ""),
    ("cp07", "Ombudsman threat", "I have got nowhere with three separate agents. If this is not resolved I will be going to the Financial Ombudsman.", "complaint", "high", False, ""),
    ("cp08", "Complaint about a dispute", "I raised a dispute six weeks ago and nobody has updated me once. That is not acceptable service.", "complaint", "high", False, "dispute mentioned, complaint intent"),
    ("cp09", "Hospital and no help", "I have been in hospital for chemotherapy and asked for a payment holiday. I was told to call back, then cut off. Twice.", "complaint", "critical", True, "health condition"),
    ("cp10", "Data error", "You have my address wrong despite three corrections and my statements are going to a previous tenant. This is a serious data issue.", "complaint", "high", False, ""),
    ("cp11", "Polite complaint", "I don't like to make a fuss, but I have been let down repeatedly over the past two months and I feel I should say something formally.", "complaint", "high", False, "polite tone, complaint intent"),
    ("cp12", "Charges after closure", "I closed the account in May and you are still applying charges to it. I want a formal response.", "complaint", "high", False, ""),
    ("cp13", "Carer struggling", "I'm a full time carer for my mother and asked for help with the arrears. Nobody has come back to me and I'm at breaking point.", "complaint", "critical", True, "carer + distress"),
    ("cp14", "Repeated failures", "Four calls, three emails, two months. Still no resolution. I would like a formal complaint raised.", "complaint", "high", False, ""),
    ("cp15", "Bereavement paperwork", "I sent the death certificate for my late wife six weeks ago as instructed and have heard nothing at all since.", "complaint", "critical", True, "bereavement"),
]

# Deliberately ambiguous. Correct behaviour is low confidence and a hold, so the
# expected type is recorded as the most defensible reading only.
AMBIGUOUS = [
    ("am01", "Question", "Hi, wondering about a charge on my account from last week, also could you send me a statement copy? Not sure who to ask.", "billing_dispute", "high", False, "mixed dispute + service request"),
    ("am02", "Help", "Need help with my account please.", "general_enquiry", "low", False, "no discernible intent"),
    ("am03", "Card", "About the card.", "general_enquiry", "low", False, "no discernible intent"),
    ("am04", "Not happy about a charge", "There's a charge I'm not happy about and frankly the whole experience has been poor.", "billing_dispute", "high", False, "dispute vs complaint genuinely unclear"),
    ("am05", "Follow up", "Following up on my previous message about the thing we discussed.", "general_enquiry", "low", False, "no context"),
]


def build():
    rows = []
    for cid, subject, text, rtype, urgency, vulnerable, note in CASES + AMBIGUOUS:
        ambiguous = cid.startswith("am")
        rows.append({
            "id": cid,
            "subject": subject,
            "text": text,
            "expected_type": rtype,
            "expected_urgency": urgency,
            "expected_vulnerable": vulnerable,
            # A hold is correct when the case is a complaint (critical), discloses
            # vulnerability, or is genuinely ambiguous.
            # A hold is correct when the case is a complaint (regulated handling),
            # discloses vulnerability, is critical, or is genuinely ambiguous.
            "expected_hold": bool(vulnerable or urgency == "critical" or ambiguous
                                  or rtype == "complaint"),
            "ambiguous": ambiguous,
            "note": note,
        })
    out = pathlib.Path(__file__).resolve().parent / "dataset.jsonl"
    out.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return rows, out


if __name__ == "__main__":
    rows, out = build()
    from collections import Counter
    print(f"wrote {len(rows)} cases to {out}")
    print("by type:    ", dict(Counter(r["expected_type"] for r in rows)))
    print("vulnerable: ", sum(r["expected_vulnerable"] for r in rows))
    print("ambiguous:  ", sum(r["ambiguous"] for r in rows))
    print("hold expected:", sum(r["expected_hold"] for r in rows))
    print("hard cases (noted):", sum(1 for r in rows if r["note"]))