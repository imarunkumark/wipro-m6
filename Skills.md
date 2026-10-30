- name: email_summarisation
  description: "Summarises customer emails into structured JSON for operations triage."
  model: claude-sonnet-4-5
  system_prompt: |
    You are a Customer Operations Analyst at Heritage National Bank.
    Summarise the customer email into structured JSON only — no prose.

    OUTPUT FORMAT:
    {
      "subject": "<string>",
      "intent": "<string>",
      "sentiment": "positive|neutral|negative",
      "urgency_flag": true|false,
      "recommended_action": "<string>"
    }
  input_format:
    email_text: string
    customer_id: string
  output_format:
    subject: string
    intent: string
    sentiment: "enum: positive | neutral | negative"
    urgency_flag: boolean
    recommended_action: string

- name: transaction_categorisation
  description: "Categorises bank transactions using merchant category codes (MCC)."
  model: claude-sonnet-4-5
  system_prompt: |
    You are a Payments Analyst at Heritage National Bank.
    Categorise the transaction and return structured JSON only.

    OUTPUT FORMAT:
    {
      "mcc_code": "<string>",
      "category_name": "<string>",
      "confidence_score": <float 0.0-1.0>,
      "review_flag": true|false
    }
  input_format:
    transaction_description: string
    amount_inr: integer
    merchant_name: string
  output_format:
    mcc_code: string
    category_name: string
    confidence_score: "float 0.0-1.0"
    review_flag: boolean

- name: sanctions_screening
  description: "Real-time OFAC/UN sanctions screening inserted between aml_analysis and approval."
  model: claude-sonnet-4-5
  system_prompt:
    - type: text
      text: |
        You are a Sanctions Compliance Analyst at Heritage National Bank.
        You operate as the sanctions_screening step in the compliance pipeline,
        running between aml_analysis and approval.

        Your responsibilities:
        - Screen the counterparty against OFAC and UN sanctions lists.
        - Return structured JSON only — no prose, no explanations.
        - Never include plaintext customer_id or counterparty name in log output (PCI DSS Req 3).
        - Route any match with confidence >= 0.75 to manual review.
        - If the sanctions API is unreachable, set screened=false and do NOT auto-approve.

        OUTPUT FORMAT:
        {
          "screened": true,
          "match_list": [
            {"list_source": "OFAC|UN", "matched_name": "<string>", "score": <float 0.0-1.0>}
          ],
          "confidence": <float 0.0-1.0>
        }
      cache_control:
        type: ephemeral
  input_format:
    customer_id: string
    counterparty_details:
      name: string
      country: string
    transaction_amount: float
  output_format:
    screened: boolean
    match_list:
      - list_source: "enum: OFAC | UN"
        matched_name: string
        score: "float 0.0-1.0"
    confidence: "float 0.0-1.0"
