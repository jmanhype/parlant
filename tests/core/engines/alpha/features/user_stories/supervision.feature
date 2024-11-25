Feature: Supervision
    Background:
        Given an empty session

    Scenario: The agent prioritizes guideline from conversation
        Given the alpha engine
        And an agent
        And a guideline "recommend_three_items", to recommend three items from "Sony WH-1000XM5, Dyson V15 Detect, Kindle Paperwhite (2024 Edition), Lego Botanical Collection, Le Creuset Dutch Oven,  Apple Watch Series 9, Fujifilm Instax Mini 12, Yeti Rambler Tumbler, Philips Hue Smart Bulbs, Theragun Mini, Bose SoundLink Flex, Hydro Flask Water Bottle, Samsung Galaxy Tab S9,  Osprey Daylite Backpack, Nintendo Switch OLED" when a user asks for recommendation for usage 
        And a customer message, "Hi there, i'm looking for something that best suit a gamer what do you have for me?"
        And an agent message, "For a gamer, I recommend the Nintendo Switch OLED for its versatile gaming experience, the Samsung Galaxy Tab S9 for gaming on the go, and the Sony WH-1000XM5 for immersive audio while gaming."
        And a customer message, "But i want the one with the best screen quality and long battery life"
        When processing is triggered
        Then a single message event is emitted
        And the message contains only one result

    Scenario: The agent prioritizes guideline from conversation with tools
        Given the alpha engine
        And an agent
        And a guideline "recommend_three", to recommend best three products when a user mentions specific needs
        And the tool "get_product_tags"
        And the tool "get_products_by_tags"
        And an association between "recommend_three" and "get_product_tags"
        And an association between "recommend_three" and "get_products_by_tags"
        And a customer message, "Hey there! I need a laptop for gaming"
        And an agent message, "Hey there! Gotcha covered—gaming laptops are in stock. Do you have any specific preferences, like budget, screen size, or performance level? If not, I can recommend three awesome options right away!"
        And a customer message, "I want to play Cyberpunk 2077 and my budget is around $2000"
        And an agent message, "Alright, based on your budget of around $2000 and your goal of playing Cyberpunk 2077, here are three great options: HP OMEN 16 RTX 4070 - $1899.99: A 16-inch gaming laptop with an AMD Ryzen 9 processor, RTX 4070 GPU, 16GB RAM, and a 1TB SSD. Perfect for high-performance gaming on a QHD display. ASUS ROG Zephyrus G14 - $1799.99: A compact 14-inch gaming laptop with an AMD Ryzen 9 processor, RTX 4070 GPU, 16GB RAM, and a 1TB SSD. Great for gaming on the go with a high-quality QHD display. ASUS TUF Gaming A15 - $1199.99: A 15-inch gaming laptop with an AMD Ryzen 7 processor, RTX 4060 GPU, 16GB RAM, and a 512GB SSD. A solid choice for gaming with excellent performance at a lower price point. Let me know if you'd like more details about any of these or need help deciding!"
        And a customer message, "im sorry i wanted to say that my budget is 600"
        And an agent message, "Oh, got it! With a budget of $600, here’s a solid option for gaming: HP Victus 15 - $799.99: A 15-inch gaming laptop with Intel i5, RTX 3050 GPU, 16GB RAM, and a 512GB SSD. It’s slightly above your budget, but it’s one of the most affordable gaming laptops available. Let me know if you’d like more details or need help finding something else!"
        And a customer message, "This is ridiculous! Why are gaming laptops so expensive? I just want to play one game!"
        And an agent message, "Whoa, I hear you! Gaming laptops can be pricey, and it’s frustrating when all you want is to play one game. Let’s look at some alternatives. Have you considered a refurbished gaming laptop or even a desktop setup, which can sometimes be more affordable? If you’re open to it, I can also help find a laptop that’s closer to your budget and still runs Cyberpunk 2077 decently."
        And a customer message, "what do you have for me?"
        When processing is triggered
        Then a single message event is emitted
        And the message contains only one result