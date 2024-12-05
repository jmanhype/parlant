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

