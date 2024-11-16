Feature: Context Variables
    Background:
        Given the alpha engine
        And an empty session

    Scenario: The agent informs the VIP user that they deserve a ten percent discount
        Given a context variable "special_discount" with the value "10%" assigned to users with the tag "VIP"
        And a guideline "discounts" to inform them about discounts that apply to them when a VIP user wants to order a pizza
        And the user is tagged as "VIP"
        And a user message, "I want to order a pizza"
        When processing is triggered
        And a single message event is emitted
        And the message contains information informing the user that they deserve a 10% discount as a VIP

    Scenario: The agent recommends only the vegetarian topping options to a vegetarian user
        Given a context variable "avoid_toppings" with the value "olives" assigned to users with the tag "allergic"
        And a guideline "check_stock" to only suggest toppings which are in stock is when suggesting pizza toppings
        And the tool "get_available_toppings"
        And an association between "check_stock" and "get_available_toppings"
        And the user is tagged as "allergic"
        And a user message, "What pizza topping should I take?"
        When processing is triggered
        Then a single tool calls event is emitted
        And a single message event is emitted
        And the message contains a recommendation for pepperoni and mushrooms while avoiding olives