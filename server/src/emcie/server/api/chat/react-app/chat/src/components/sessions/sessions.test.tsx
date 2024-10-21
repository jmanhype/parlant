import { cleanup, MatcherOptions, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import Sessions from "./sessions.tsx";
import '@testing-library/jest-dom/vitest';
import { Matcher } from "vite";

const sessionsArr = [
    { id: 'session1', title: 'Session One' },
    { id: 'session2', title: 'Session Two' }
];

vi.mock('@/hooks/useFetch', () => ({
    default: () => {
        return {
            data: {sessions: sessionsArr},
            refetch: vi.fn()
        }
    }
}));

describe('Sessions Component', () => {
    let getAllByTestId: (id: Matcher, options?: MatcherOptions | undefined) => HTMLElement[];
    let getByTestId: (id: Matcher, options?: MatcherOptions | undefined) => HTMLElement;
    let sessions: HTMLElement;
    let session: HTMLElement[];
    
    beforeEach(() => {
        const utils = render(<Sessions agentId="" setSession={vi.fn()} sessionId="session1"/>);
        getAllByTestId = utils.getAllByTestId as (id: Matcher, options?: MatcherOptions | undefined) => HTMLElement[];
        getByTestId = utils.getByTestId as (id: Matcher, options?: MatcherOptions | undefined) => HTMLElement;
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
});