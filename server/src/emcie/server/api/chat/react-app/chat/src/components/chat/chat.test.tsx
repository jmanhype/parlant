import { describe, expect, it, vi } from 'vitest';
import { act, fireEvent, MatcherOptions, render } from '@testing-library/react';
import { Matcher } from 'vite';
import Chat from './chat';
import { postData } from '@/utils/api';
import { SessionProvider } from '../chatbot/chatbot';
import { ReactElement } from 'react';


vi.mock('@/utils/api', () => ({
    postData: vi.fn(() => Promise.resolve())
}));


describe('Chat - New Session', () => {
    let getByRole: (id: Matcher, options?: MatcherOptions | undefined) => HTMLElement;
    beforeEach(async () => {
        vi.clearAllMocks();
        vi.resetModules();
        await act(() => {
            const utils = render(<Chat/>);
            getByRole = utils.getByRole as (id: Matcher, options?: MatcherOptions | undefined) => HTMLElement;
        });
    });

    it('component should be rendered', () => {
        const submitButton = getByRole('button');
        expect(submitButton).toBeInTheDocument();
    });

    it('submit button should be initially disabled', () => {
        const submitBtn = getByRole('button');
        expect(submitBtn).toBeDisabled();
    });

    it('submit button should be disabled when typing and no agent is selected', async () => {
        const submitBtn = getByRole('button');
        const textarea = getByRole('textbox');
        await act(async () => fireEvent.change(textarea, {target: {value: 'hello'}}));
        expect(submitBtn).toBeDisabled();
    });
});

describe('Chat - Existing Session', () => {
    const MockSessionProvider = ({ children }: {children: ReactElement}) => (
        <SessionProvider.Provider
        value={{
            sessionId: '213',
            setSessionId: vi.fn(),
            agentId: '123',
            setAgentId: vi.fn(),
            newSession: null,
            setNewSession: vi.fn(),
            sessions: [],
            setSessions: vi.fn()
        }}>{children}</SessionProvider.Provider>
    );
    let getByRole: (id: Matcher, options?: MatcherOptions | undefined) => HTMLElement;
    let getByTestId: (id: Matcher, options?: MatcherOptions | undefined) => HTMLElement;
    beforeEach(async () => {
        vi.clearAllMocks();
        vi.resetModules();
        await act(() => {
            const utils = render(<MockSessionProvider><Chat/></MockSessionProvider>);
            getByRole = utils.getByRole as (id: Matcher, options?: MatcherOptions | undefined) => HTMLElement;
            getByTestId = utils.getByTestId as (id: Matcher, options?: MatcherOptions | undefined) => HTMLElement;
        });
    });
    it('submit button should be enabled when typing and there is an agent selected', async () => {
        const textarea = getByRole('textbox');
        await act(async () => fireEvent.change(textarea, {target: {value: 'hello'}}));
        const submitBtn = getByTestId('submit-button');
        expect(submitBtn).toBeEnabled();
    });

    it('clicking submit triggers the post event and clears the input', async () => {
        const submitBtn = getByRole('button');
        const textarea = getByRole('textbox');
        await act(async () => {
            fireEvent.change(textarea, {target: {value: 'hello'}});
            fireEvent.click(submitBtn);
        });
        expect(postData).toBeCalled();
        expect(textarea).toHaveTextContent('');
        expect(submitBtn).toBeDisabled();
    });
});