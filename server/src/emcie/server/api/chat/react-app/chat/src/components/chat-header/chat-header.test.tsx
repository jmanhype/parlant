import { describe, it, vi } from 'vitest';
import ChatHeader, { NEW_SESSION_ID } from './chat-header';
import { fireEvent, MatcherOptions, render } from '@testing-library/react';
import { Matcher } from 'vite';

const setSessionFn = vi.fn();
vi.mock('react', async () => {
    const actualReact = await vi.importActual('react');
    return {
        ...actualReact,
        useContext: vi.fn(() => ({setSessionId: setSessionFn, setAgentId: vi.fn(), setNewSession: vi.fn()}))
    };
});

describe(ChatHeader, () => {
    let getByRole: (id: Matcher, options?: MatcherOptions | undefined) => HTMLElement;

    beforeEach(() => {
        const utils = render(<ChatHeader />);
        getByRole = utils.getByRole as (id: Matcher, options?: MatcherOptions | undefined) => HTMLElement;

        vi.clearAllMocks();
    });

    it('clicking the "add session" button should create a new mocked session', async () => {
        const addBtn = getByRole('button');
        fireEvent.click(addBtn);
        expect(setSessionFn).toHaveBeenCalledWith(NEW_SESSION_ID);
    });
});