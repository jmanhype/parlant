import { describe, expect, it, vi } from "vitest";
import SessionControl from "./session-control";
import { act, fireEvent, MatcherOptions, render } from "@testing-library/react";
import { Matcher } from "vite";
import { postData } from "@/utils/api";

vi.mock('@/utils/api', () => ({
    postData: vi.fn(() => Promise.resolve({session: {}}))
}));

vi.mock("../agents-select/agents-select", () => ({
    default: ({ setSelectedAgent }: {setSelectedAgent: (text: string) => void}) => (
        <select onChange={(e) => setSelectedAgent(e.target.value)} data-testid="agent-select">
            <option value="agent1">Agent One</option>
        </select>
    )
}));

describe('Session Control Component', () => {
    let getByRole: (id: Matcher, options?: MatcherOptions | undefined) => HTMLElement;
    let getByTestId: (id: Matcher, options?: MatcherOptions | undefined) => HTMLElement;
    
    beforeEach(() => {
        const utils = render(<SessionControl sessionId={null} setSession={vi.fn()}/>);
        getByRole = utils.getByRole as (id: Matcher, options?: MatcherOptions | undefined) => HTMLElement;
        getByTestId = utils.getByTestId as (id: Matcher, options?: MatcherOptions | undefined) => HTMLElement;
    });

    it('component should be rendered', () => {
        const addButton = getByRole('button');
        expect(addButton).toBeInTheDocument();
    });

    it('"add session" button should be disabled when no agent selected', async () => {
        const addButton = getByRole('button');
        expect(addButton).toBeDisabled();
    });

    it('"add session" button should be enabled when an agent is selected', async () => {
        const addButton = getByRole('button');
        const select = getByTestId('agent-select');
        await act(async () => fireEvent.change(select, {target: {value: 'agent1'}}));
        expect(addButton).toBeEnabled();
    });
    
    it('clicking the "add session" button should create a call to the server', async () => {
        const addButton = getByRole('button');
        const select = getByTestId('agent-select');
        await act(async () => {
            fireEvent.change(select, {target: {value: 'agent1'}});
            fireEvent.click(addButton);
        });
        expect(postData).toBeCalled();
    });
});