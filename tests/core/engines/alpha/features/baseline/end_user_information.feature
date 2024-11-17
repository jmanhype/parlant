Feature: End User Information
    Background:
        Given the alpha engine

    Scenario: The agent proposes guidelines based on user tags and context variable
        Given an empty session
        And a context variable "special_discount" with the value "10%" assigned to users with the tag "VIP"
        And a guideline "discounts" to inform them about discounts that apply to them when a VIP user wants to order a pizza
        And the user is tagged as "VIP"
        And a user message, "I want to order a pizza"
        When processing is triggered
        Then a single message event is emitted
        And the message contains information informing the user that they deserve a 10% discount as a VIP

    Scenario: The agent proposes guidelines based on the users name
        Given an empty session with "Bubbles"
        And a guideline "b_names" to tell them they are not welcome at the club when a user whose name starts with B wants to get into the club
        And a user message, "Can you let me into the club?"
        When processing is triggered
        Then a single message event is emitted
        And the message contains that the user cannot be let into the club

    Scenario: The agent considers user tags when formulating response
        Given an empty session
        And a context variable "avoid_toppings" with the value "olives" assigned to users with the tag "allergic"
        And a guideline "check_stock" to only suggest toppings which are in stock is when suggesting pizza toppings
        And the tool "get_available_toppings"
        And an association between "check_stock" and "get_available_toppings"
        And a user message, "What pizza topping should I take?"
        When processing is triggered
        Then a single tool calls event is emitted
        And a single message event is emitted
        And the message contains a recommendation for pepperoni and mushrooms while avoiding olives

    Scenario: The agent considers many tags when formulating response
        Given an empty session with "Rawls"
        And a context variable "avoid_topping_1" with the value "olives" assigned to users with the tag "allergic"
        And a context variable "avoid_topping_2" with the value "pepperoni" assigned to users with the tag "vegetarian"
        And a guideline "check_stock" to only suggest toppings which are in stock is when suggesting pizza toppings
        And the tool "get_available_toppings"
        And an association between "check_stock" and "get_available_toppings"
        And the user is tagged as "allergic"
        And the user is tagged as "vegetarian"
        And a user message, "What pizza topping should I take?"
        When processing is triggered
        Then a single tool calls event is emitted
        And a single message event is emitted
        And the message contains a recommendation for mushrooms while avoiding olives and pepperoni

    Scenario: The agent considers the users name when formulating response
        Given an empty session with "Naymond Brice"
        And a user message, "What's my name?"
        When processing is triggered
        Then a single message event is emitted
        And the message contains the name Naymond Brice

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

    Scenario: The agent considers users name when calling tools
        Given an empty session with "Dukie"
        And the user is tagged as "underage"
        And a guideline "check_name" to check if an underage user can register to the service based on their name when the user asks if they can register to our service
        And the tool "check_username_validity"
        And an association between "check_name" and "check_username_validity"
        And a user message, "Can I sign up with you guys?"
        When processing is triggered
        Then a single message event is emitted
        And the message contains a negative reply

    Scenario: The agent correctly deduces information based on tags
        Given an empty session with "Dukie"
        And the user is tagged as "underage"
        And a guideline "check_name" to check if an adult user can register to the service based on their name when an adult user asks if they can register to our service
        And the tool "check_username_validity"
        And a guideline "underage_allowed" to reply positively when asked by an underage user if they can join our service
        And an association between "check_name" and "check_username_validity"
        And a user message, "Can I sign up with you guys?"
        When processing is triggered
        Then a single message event is emitted
        And the message contains a positive reply

    Scenario: The agent considers many tags when formulating response
        Given an empty session with "Bob"
        And a context variable "avoid_topping_1" with the value "olives" assigned to users with the tag "allergic"
        And a context variable "avoid_topping_2" with the value "pepperoni" assigned to users with the tag "vegetarian"
        And a guideline "check_stock" to only suggest toppings which are in stock is when suggesting pizza toppings
        And the tool "get_available_toppings"
        And an association between "check_stock" and "get_available_toppings"
        And the user is tagged as "allergic"
        And the user is tagged as "vegetarian"
        And a user message, "What pizza topping should I take?"
        When processing is triggered
        Then a single tool calls event is emitted
        And a single message event is emitted
        And the message contains a recommendation for mushrooms while avoiding olives and pepperoni
