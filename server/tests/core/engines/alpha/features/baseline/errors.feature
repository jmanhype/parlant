    Scenario: Failure to process a message emits an error status
        Given the alpha engine
        And a nonexistent agent
        And a session with a single user message
        When processing is triggered
        Then a status event is emitted, encountering an error while processing event 0
