Feature: Tools
    Background:
        Given the alpha engine
        And an agent

    Scenario: Tool called again by context after customer response
        Given an empty session
        And a guideline "retrieve_account_information" to retrieve account information when customers inquire about account-related information
        And the tool "get_account_balance"
        And an association between "retrieve_account_information" and "get_account_balance"
        And a customer message, "What is the balance of Larry David's account?"
        And a tool event with data, { "tool_calls": [{ "tool_id": "local:get_account_balance", "arguments": { "account_name": "Larry David"}, "result": { "data": 451000000, "metadata": {} }}]}
        And an agent message, "Larry David currently has 451 million dollars."
        And a customer message, "And what about now?"
        When processing is triggered
        Then a single tool calls event is emitted
        And the tool calls event contains 1 tool call(s)
        And the tool calls event contains a call to "get_account_balance" with Larry David's current balance

    Scenario: Tool caller does not over-optimistically assume an argument's value
        Given a customer with the name "Vax"
        And an empty session with "Vax"
        And a context variable "Current Date" set to "January 17th, 2025" for "Vax"
        And a guideline "pay_cc_bill_guideline" to help a customer make the payment when they want to pay their credit card bill
        And the tool "pay_cc_bill"
        And an association between "pay_cc_bill_guideline" and "pay_cc_bill"
        And a customer message, "Let's please pay my credit card bill"
        When processing is triggered
        Then no tool calls event is emitted

    Scenario: Tool caller correctly infers an argument's value (1)
        Given a customer with the name "Vax"
        And an empty session with "Vax"
        And a context variable "Current Date" set to "January 17th, 2025" for "Vax"
        And a guideline "pay_cc_bill_guideline" to help a customer make the payment when they want to pay their credit card bill
        And the tool "pay_cc_bill"
        And an association between "pay_cc_bill_guideline" and "pay_cc_bill"
        And a customer message, "Let's please pay my credit card bill immediately"
        When processing is triggered
        Then a single tool calls event is emitted
        And the tool calls event contains 1 tool call(s)
        And the tool calls event contains a call to "pay_cc_bill" with date 17-01-2025

    Scenario: Tool caller correctly infers an argument's value (2)
        Given a customer with the name "Vax"
        And an empty session with "Vax"
        And a context variable "Current Date" set to "January 17th, 2025" for "Vax"
        And a guideline "pay_cc_bill_guideline" to help a customer make the payment when they want to pay their credit card bill
        And the tool "pay_cc_bill"
        And an association between "pay_cc_bill_guideline" and "pay_cc_bill"
        And a customer message, "Let's please pay my credit card bill. Payment date is tomorrow."
        When processing is triggered
        Then a single tool calls event is emitted
        And the tool calls event contains 1 tool call(s)
        And the tool calls event contains a call to "pay_cc_bill" with date 18-01-2025

    Scenario: Guideline proposer and tool caller understand that a Q&A tool needs to be called multiple times to answer different questions
        Given an empty session
        And a guideline "answer_questions" to look up the answer and, if found, when the customer has a question related to the bank's services
        And the tool "find_answer"
        And an association between "answer_questions" and "find_answer"
        And a customer message, "How do I pay my credit card bill?"
        And an agent message, "You can just tell me the last 4 digits of the desired card and I'll help you with that."
        And a customer message, "Thank you! And I imagine this applies also if my card is currently lost, right?"
        When processing is triggered
        Then a single tool calls event is emitted
        And the tool calls event contains 1 tool call(s)
        And the tool calls event contains a call to "find_answer" with an inquiry about a situation in which a card is lost
