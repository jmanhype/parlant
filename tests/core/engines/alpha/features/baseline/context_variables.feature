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

