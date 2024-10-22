import { cleanup, MatcherOptions, render, SelectorMatcherOptions } from '@testing-library/react';
import { describe, expect, it, Mock, vi } from 'vitest';
import Sessions from './sessions.tsx';
import '@testing-library/jest-dom/vitest';
import { Matcher } from 'vite';
import useFetch from '@/hooks/useFetch.tsx';

const sessionsArr = [
    { id: 'session1', title: 'Session One' },
    { id: 'session2', title: 'Session Two' }
];

vi.mock('@/hooks/useFetch', () => ({
    default: vi.fn(() => {
        return {
            data: {sessions: sessionsArr},
            refetch: vi.fn()
        };
    })
}));

describe(Sessions, () => {
    let getAllByTestId: (id: Matcher, options?: MatcherOptions | undefined) => HTMLElement[];
    let getByTestId: (id: Matcher, options?: MatcherOptions | undefined) => HTMLElement;
    let getByText: (id: Matcher, options?: SelectorMatcherOptions | undefined) => HTMLElement;
    let sessions: HTMLElement;
    let session: HTMLElement[];
    let rerender: (ui: React.ReactNode) => void;
    
    beforeEach(() => {
        const utils = render(<Sessions agentId=''/>);
        getAllByTestId = utils.getAllByTestId as (id: Matcher, options?: MatcherOptions | undefined) => HTMLElement[];
        getByTestId = utils.getByTestId as (id: Matcher, options?: MatcherOptions | undefined) => HTMLElement;
        getByText = utils.getByText as (id: Matcher, options?: SelectorMatcherOptions | undefined) => HTMLElement;
        rerender = utils.rerender;
        sessions = getByTestId('sessions');
        session = getAllByTestId('session');
    });

    afterEach(() => cleanup());

    it('component should be rendered', () => {
        expect(sessions).toBeInTheDocument();
    });

    it('component should have 2 sessions', () => {
        expect(session).toHaveLength(2);
    });

    it('component should show a loading indication on loading', () => {
        (useFetch as Mock).mockImplementationOnce(() => ({
            data: {sessions: sessionsArr},
            loading: true,
            refetch: vi.fn()
        }));
        rerender(<Sessions agentId=''/>);
        const loading = getByText('loading...');
        expect(loading).toBeInTheDocument();
    });

    it('component should show error when it gets one', () => {
        (useFetch as Mock).mockImplementationOnce(() => ({
            data: {sessions: sessionsArr},
            ErrorTemplate: () => <div>error</div>,
            refetch: vi.fn()
        }));
        rerender(<Sessions agentId=''/>);
        const error = getByText('error');
        expect(error).toBeInTheDocument();
    });
});