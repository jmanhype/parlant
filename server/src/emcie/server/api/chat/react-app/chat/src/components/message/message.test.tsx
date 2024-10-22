import { describe, expect, it } from 'vitest';
import { MatcherOptions, render } from '@testing-library/react';
import { Matcher } from 'vite';
import Message from './message';
import { Event, ServerStatus } from '../chat/chat';

const serverStatuses: ServerStatus[] = ['pending', 'error', 'accepted', 'acknowledged', 'processing', 'typing', 'ready'];

const event: Event = {
    correlation_id: '',
    creation_utc: new Date(),
    data: {message: 'Hi'},
    kind: 'message',
    offset: 0,
    serverStatus: 'pending',
    source: 'client'
};

describe(Message, () => {
    let getByTestId: (id: Matcher, options?: MatcherOptions | undefined) => HTMLElement;
    let rerender: (ui: React.ReactNode) => void;
    
    beforeEach(() => {
        const utils = render(<Message event={event}/>);
        getByTestId = utils.getByTestId as (id: Matcher, options?: MatcherOptions | undefined) => HTMLElement;
        rerender = utils.rerender;
    });

    it('component should be rendered', () => {
        const message = getByTestId('message');
        expect(message).toBeInTheDocument();
    });

    it('message has the valid icon', () => {
        for (const serverStatus of serverStatuses) {
            rerender(<Message event={{...event, serverStatus}}/>);
            const icon = getByTestId(serverStatus);
            expect(icon).toBeInTheDocument();
        }
    });
});