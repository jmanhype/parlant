import { describe, expect, it } from "vitest";
import { MatcherOptions, render } from "@testing-library/react";
import { Matcher } from "vite";
import Message from "./message";
import { Event } from "../chat/chat";

const event: Event = {
    correlation_id: '',
    creation_utc: new Date(),
    data: {message: 'Hi'},
    kind: 'message',
    offset: 0,
    serverStatus: 'pending',
    source: 'client'
};

describe('Message Component', () => {
    let getByTestId: (id: Matcher, options?: MatcherOptions | undefined) => HTMLElement;
    
    beforeEach(() => {
        const utils = render(<Message event={event}/>);
        getByTestId = utils.getByTestId as (id: Matcher, options?: MatcherOptions | undefined) => HTMLElement;
    });

    it('component should be rendered', () => {
        const message = getByTestId('message');
        expect(message).toBeInTheDocument();
    });
});