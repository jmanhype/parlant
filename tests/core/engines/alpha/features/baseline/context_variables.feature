Feature: Context Variables
    Background:
        Given the alpha engine

    Scenario: The agent does not acknowledge values from other users when the user lacks a value
        Given an end user with the name "Keyleth"
        And an end user with the name "Vax"
        And a context variable "Power" with a value of "Stealth" to "Vax"
        And an empty session with "Keyleth"
        And a user message, "Do you know my power?"
        When processing is triggered
        Then a single message event is emitted
        And the message contains a response that does not indicate the user’s power is stealth

    Scenario: The agent selects variables that are specifically attached to the relevant user
        Given an end user with the name "Keyleth"
        And an end user with the name "Vax"
        And a context variable "Power" with a value of "Magic" to "Keyleth"
        And a context variable "Power" with a value of "Stealth" to "Vax"
        And an empty session with "Vax"
        And a user message, "Do you know my power?"
        When processing is triggered
        Then a single message event is emitted
        And the message contains no acknowledgment of the user’s power

    Scenario: The agent selects variables that are specifically attached to the relevant user
        Given an end user with the name "Keyleth"
        And an end user with the name "Vax"
        And a context variable "Power" with a value of "Magic" to "Keyleth"
        And a context variable "Power" with a value of "Stealth" to "Vax"
        And an empty session with "Vax"
        And a user message, "Do you know my power?"
        When processing is triggered
        Then a single message event is emitted
        And the message mentions to the user that their power is Stealth

    Scenario: The agent proposes guidelines based on user tags and context variable
        Given an empty session
        And a context variable "service level" with the value "permium" assigned to the tag "VIP"
        And a guideline "premium" to greet the user with 'Howdy' when the user is in service level of premium
        And the user is tagged as "VIP"
        And a user message, "Hey there"
        When processing is triggered
        Then a single message event is emitted
        And the message contains a 'Howdy' greeting

    Scenario: The agent considering multiple values for the same context variable assigned to the same tag
        Given an empty session
        And a context variable "discount eligibility" with the value "10% off" assigned to the tag "VIP"
        And a context variable "discount eligibility" with the value "priority shipping" assigned to the tag "VIP"
        And the user is tagged as "VIP"
        And a user message, "What benefits do I have?"
        When processing is triggered
        Then a single message event is emitted
        And the message contains both "10% off" and "priority shipping" as part of the user's benefits

    Scenario: The agent considers tags when calling tools
        Given an empty session with "Dukie"
        And the user is tagged as "underage"
        And a guideline "suggest_drink_guideline" to suggest a drink based on the drink recommendation tool when the user asks for drink recommendation
        And the tool "recommend_drink"
        And an association between "suggest_drink_guideline" and "recommend_drink"
        And a user message, "What drink should I get?"
        When processing is triggered
        Then a single message event is emitted
        And the message contains a recommendation for soda

