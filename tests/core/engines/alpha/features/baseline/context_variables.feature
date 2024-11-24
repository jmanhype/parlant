Feature: Context Variables
    Background:
        Given the alpha engine

    Scenario: The agent does not acknowledge values from other customers when the customer lacks a value
        Given a customer with the name "Keyleth"
        And a customer with the name "Vax"
        And a context variable "Power" set to "Stealth" to "Vax"
        And an empty session with "Keyleth"
        And a customer message, "Do you know my power?"
        When processing is triggered
        Then a single message event is emitted
        And the message contains no acknowledgment of the customer’s power

    Scenario: The agent selects variables that are specifically attached to the relevant customer
        Given a customer with the name "Keyleth"
        And a customer with the name "Vax"
        And a context variable "Power" set to "Magic" to "Keyleth"
        And a context variable "Power" set to "Stealth" to "Vax"
        And an empty session with "Vax"
        And a customer message, "Do you know my power?"
        When processing is triggered
        Then a single message event is emitted
        And the message mentions to the customer that their power is Stealth

    Scenario: The agent proposes guidelines based on customer tags and context variable
        Given an empty session
        And a customer tagged as "VIP"
        And a context variable "service level" set to "permium" for the tag "VIP"
        And a guideline "service_level" to tell the customer what their service level is when the customer asking for the service level
        And a customer message, "What service level am I?"
        When processing is triggered
        Then a single message event is emitted
        And the message mentions the customer's service level as premium

    Scenario: The agent considering customer value rather customer tag value
        Given an empty session
        And a customer tagged as "VIP"
        And a context variable "service level" set to "permium" for the tag "VIP"
        And a context variable "service level" set to "elite"
        And a customer message, "What service level am I?"
        When processing is triggered
        Then a single message event is emitted
        And the message mentions the customer service level is elite
    
    Scenario: The agent considers tags when calling tools
        Given an empty session with "Dukie"
        And a customer tagged as "underage"
        And a context variable "age_restriction" set to "non-alcoholic" for the tag "underage"
        And a guideline "suggest_drink_guideline" to suggest a drink based on the drink recommendation tool when the customer asks for drink recommendation
        And the tool "recommend_drink"
        And an association between "suggest_drink_guideline" and "recommend_drink"
        And a customer message, "What drink should I get?"
        When processing is triggered
        Then a single message event is emitted
        And the message contains a recommendation for soda

