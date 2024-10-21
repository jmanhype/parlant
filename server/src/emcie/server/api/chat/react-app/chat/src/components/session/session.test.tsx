import { cleanup, fireEvent, MatcherOptions, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import '@testing-library/jest-dom/vitest';
import { Matcher } from "vite";
import Session from "./session";
import { Session as SessionInterface } from "../sessions/sessions";
import { deleteData } from "@/utils/api";

const session: SessionInterface | null = { id: 'session1', title: 'Session One', end_user_id: '' };


vi.mock('@/utils/api', () => ({
    deleteData: vi.fn(() => Promise.resolve()),
}))


describe('Session Component', () => {
    let getByTestId: (id: Matcher, options?: MatcherOptions | undefined) => HTMLElement;
    let rerender: (ui: React.ReactNode) => void;
    let container: HTMLElement;
    const setSession = vi.fn();
    
    beforeEach(() => {
        const utils = render(<Session setSession={setSession} session={session as SessionInterface} refetch={vi.fn()} isSelected={true}/>);
        getByTestId = utils.getByTestId as (id: Matcher, options?: MatcherOptions | undefined) => HTMLElement;
        rerender = utils.rerender;
        container = utils.container;

        vi.clearAllMocks();
    });

    afterEach(() => cleanup());

    it('component should be rendered', () => {
        const div = getByTestId('session');
        expect(div).toBeInTheDocument();
    });

    it('unselected session should have delete and edit buttons', () => {
        const editBtn = getByTestId('edit');
        expect(editBtn).toBeInTheDocument();
        const deleteBtn = getByTestId('delete');
        expect(deleteBtn).toBeInTheDocument();
    });

    it('delete button should work as expected', async () => {
        const deleteBtn = getByTestId('delete');
        await fireEvent.click(deleteBtn);
        expect(deleteData).toBeCalled();
    });

    it('active session should be closed if deleted', async () => {
        const deleteBtn = getByTestId('delete');
        await fireEvent.click(deleteBtn);
        expect(setSession).toBeCalledWith(null);
    });

    it('inactive session should not be closed if deleted', async () => {
        rerender(<Session setSession={setSession} session={session as SessionInterface} refetch={vi.fn()} isSelected={false}/>)
        const deleteBtn = getByTestId('delete');
        await fireEvent.click(deleteBtn);
        expect(setSession).not.toBeCalled();
    });

    it('text field opened when "edit" button is clicked', () => {
        const editBtn = getByTestId('edit');
        fireEvent.click(editBtn);
        const textfields = container.querySelector('input');
        expect(textfields).toBeInTheDocument();
    });

    it('text field closed when "cancel edit" button is clicked', () => {
        const editBtn = getByTestId('edit');
        fireEvent.click(editBtn);
        const textfields = container.querySelector('input');
        expect(textfields).toBeInTheDocument();
        const cancelBtn = getByTestId('cancel');
        fireEvent.click(cancelBtn);
        expect(textfields).not.toBeInTheDocument();
    });
});