Feature: Context Variables
    Background:
        Given the alpha engine

    Scenario: The agent does not acknowledge values from other users when the user lacks a value
        Given an end user with the name "Keyleth"
        And an end user with the name "Vax"
        And a context variable "Power" with a value "Stealth" to "Vax"
        And an empty session with "Keyleth"
        And a user message, "Do you know my power?"
        When processing is triggered
        Then a single message event is emitted
        And the message contains no acknowledgment of the user’s power

    Scenario: The agent selects variables that are specifically attached to the relevant user
        Given an end user with the name "Keyleth"
        And an end user with the name "Vax"
        And a context variable "Power" with a value "Magic" to "Keyleth"
        And a context variable "Power" with a value "Stealth" to "Vax"
        And an empty session with "Vax"
        And a user message, "Do you know my power?"
        When processing is triggered
        Then a single message event is emitted
        And the message mentions to the user that their power is Stealth

    Scenario: The agent proposes guidelines based on user tags and context variable
        Given an empty session
        And the user is tagged as "VIP"
        And a context variable "service level" with a value "permium" to tag "VIP"
        And a guideline "premium" to greet the user with 'Howdy' when the user is in service level of premium
        And a user message, "Hey there"
        When processing is triggered
        Then a single message event is emitted
        And the message contains a 'Howdy' greeting

    Scenario: The agent considering user value rather user tag value
        Given an empty session
        And the user is tagged as "VIP"
        And a context variable "service level" with a value "permium" to tag "VIP"
        And a context variable "service level" with a value "elite"
        And a user message, "What service level am I?"
        When processing is triggered
        Then a single message event is emitted
        And the message mentions the user service level is elite
    
    Scenario: The agent considers tags when calling tools
        Given an empty session with "Dukie"
        And the user is tagged as "underage"
        And a context variable "age_restriction" with a value "non-alcoholic" to tag "underage"
        And a guideline "suggest_drink_guideline" to suggest a drink based on the drink recommendation tool when the user asks for drink recommendation
        And the tool "recommend_drink"
        And an association between "suggest_drink_guideline" and "recommend_drink"
        And a user message, "What drink should I get?"
        When processing is triggered
        Then a single message event is emitted
        And the message contains a recommendation for soda

