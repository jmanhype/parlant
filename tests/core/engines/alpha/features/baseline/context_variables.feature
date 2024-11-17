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

    Scenario: The agent informs the VIP user that they deserve a ten percent discount
        Given an empty session
        And a context variable "special_discount" with the value "10%" assigned to users with the tag "VIP"
        And a guideline "discounts" to inform them about discounts that apply to them when a VIP user wants to order a pizza
        And the user is tagged as "VIP"
        And a user message, "I want to order a pizza"
        When processing is triggered
        Then a single message event is emitted
        And the message contains information informing the user that they deserve a 10% discount as a VIP

    Scenario: The agent recommends only the vegetarian topping options to a vegetarian user
        Given an empty session
        And a context variable "avoid_toppings" with the value "olives" assigned to users with the tag "allergic"
        And a guideline "check_stock" to only suggest toppings which are in stock is when suggesting pizza toppings
        And the tool "get_available_toppings"
        And an association between "check_stock" and "get_available_toppings"
        And the user is tagged as "allergic"
        And a user message, "What pizza topping should I take?"
        When processing is triggered
        Then a single tool calls event is emitted
        And a single message event is emitted
        And the message contains a recommendation for pepperoni and mushrooms while avoiding olives