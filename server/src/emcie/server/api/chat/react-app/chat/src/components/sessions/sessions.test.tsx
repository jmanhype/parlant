import { act, cleanup, fireEvent, MatcherOptions, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import Sessions from "./sessions.tsx";
import '@testing-library/jest-dom/vitest';
import { Matcher } from "vite";

let sessionsArr = [
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
}))

vi.mock('@/utils/api', () => ({
    deleteData: async () => {
        sessionsArr.shift();
        return;
    },
}))


describe('Sessions Component', () => {
    let getAllByTestId: (id: Matcher, options?: MatcherOptions | undefined) => HTMLElement[];
    let findAllByTestId: (id: Matcher, options?: MatcherOptions | undefined) => Promise<HTMLElement[]>;
    let getByTestId: (id: Matcher, options?: MatcherOptions | undefined) => HTMLElement;
    let container: HTMLElement;
    let sessions: HTMLElement[];
    
    beforeEach(() => {
        sessionsArr = [
            { id: 'session1', title: 'Session One' },
            { id: 'session2', title: 'Session Two' }
        ];
        const utils = render(<Sessions agentId="" setSession={vi.fn()} sessionId="session1"/>);
        getAllByTestId = utils.getAllByTestId as (id: Matcher, options?: MatcherOptions | undefined) => HTMLElement[];
        findAllByTestId = utils.findAllByTestId as (id: Matcher, options?: MatcherOptions | undefined) => Promise<HTMLElement[]>;
        getByTestId = utils.getByTestId as (id: Matcher, options?: MatcherOptions | undefined) => HTMLElement;
        container = utils.container;
        sessions = getAllByTestId('session');
    });

    afterEach(() => cleanup());

    it('component should be rendered', () => {
        expect(sessions[0]).toBeInTheDocument();
    });

    it('component should have 2 sessions', () => {
        expect(sessions).toHaveLength(2);
    });

    it('unselected session should have delete and edit buttons', () => {
        const buttons = sessions[0].querySelectorAll('button');
        expect(buttons).toHaveLength(2);
    });

    it.skip('delete button should work as expected', async () => {
        const buttons = sessions[0].querySelectorAll('button');
        act(() => {
            fireEvent.click(buttons[1]);
        });
        await new Promise(r => setTimeout(r, 0));
        const updatedSessions = await findAllByTestId('session');
        expect(updatedSessions).toHaveLength(1);
    });

    it('text field opened when "edit" button is clicked', () => {
        const buttons = sessions[0].querySelectorAll('button');
        fireEvent.click(buttons[0]);
        const textfield = getByTestId('sessionTitle');
        expect(textfield).toBeInTheDocument();
    });

    it('text field closed when "cancel edit" button is clicked', () => {
        const buttons = sessions[0].querySelectorAll('button');
        fireEvent.click(buttons[0]);
        const editButtons = sessions[0].querySelectorAll('button');
        fireEvent.click(editButtons[0]);
        const textfields = container.querySelector('input');
        expect(textfields).not.toBeInTheDocument();
    });
});