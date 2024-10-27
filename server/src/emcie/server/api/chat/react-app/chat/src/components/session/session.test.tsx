import { cleanup, fireEvent, MatcherOptions, render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { Matcher } from 'vite';
import Session from './session';
import { deleteData } from '@/utils/api';
import { SessionInterface } from '@/utils/interfaces';
import userEvent from '@testing-library/user-event';

const session: SessionInterface | null = { id: 'session1', title: 'Session One', end_user_id: '', agent_id: '', creation_utc: new Date().toLocaleString()};

vi.mock('@/utils/api', () => ({
    deleteData: vi.fn(() => Promise.resolve()),
}));

const setSessionFn = vi.fn();
vi.mock('react', async () => {
    const actualReact = await vi.importActual('react');
    return {
        ...actualReact,
        useContext: vi.fn(() => ({setSessionId: setSessionFn, setAgentId: vi.fn()}))
    };
});

describe(Session, () => {
    let getByTestId: (id: Matcher, options?: MatcherOptions | undefined) => HTMLElement;
    let rerender: (ui: React.ReactNode) => void;
    let container: HTMLElement;
    
    beforeEach(() => {
        const utils = render(<Session editingTitle={null} setEditingTitle={vi.fn()} session={session as SessionInterface} refetch={vi.fn()} isSelected={true}/>);
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

    it('delete button should work as expected', async () => {
        const moreBtn = getByTestId('menu-button');
        await userEvent.click(moreBtn);
        const deleteBtn = getByTestId('delete');
        await fireEvent.click(deleteBtn);
        expect(deleteData).toBeCalled();
    });

    it('active session should be closed if deleted', async () => {
        const moreBtn = getByTestId('menu-button');
        await userEvent.click(moreBtn);
        const deleteBtn = getByTestId('delete');
        await fireEvent.click(deleteBtn);
        expect(setSessionFn).toBeCalledWith(null);
    });

    it('inactive session should not be closed if deleted', async () => {
        rerender(<Session editingTitle={null} setEditingTitle={vi.fn()} session={session as SessionInterface} refetch={vi.fn()} isSelected={false}/>);
        const moreBtn = getByTestId('menu-button');
        await userEvent.click(moreBtn);
        const deleteBtn = getByTestId('delete');
        await fireEvent.click(deleteBtn);
        expect(setSessionFn).not.toBeCalled();
    });

    it('text field opened when editing the current session', async () => {
        rerender(<Session editingTitle={session.id} setEditingTitle={vi.fn()} session={session as SessionInterface} refetch={vi.fn()} isSelected={false}/>);
        const textfields = container.querySelector('input');
        expect(textfields).toBeInTheDocument();
    });

    it('text field closed when "cancel edit" button is clicked', async () => {
        const setEditingTitleFn = vi.fn();
        rerender(<Session editingTitle={session.id} setEditingTitle={setEditingTitleFn} session={session as SessionInterface} refetch={vi.fn()} isSelected={false}/>);
        const cancelBtn = getByTestId('cancel');
        fireEvent.click(cancelBtn);
        expect(setEditingTitleFn).toBeCalledWith(null);
    });

    it('session should be enabled when not editing another session', async () => {
        rerender(<Session editingTitle={null} setEditingTitle={vi.fn()} session={session as SessionInterface} refetch={vi.fn()} isSelected={false}/>);
        const currSession = getByTestId('session');
        fireEvent.click(currSession);
        expect(setSessionFn).toBeCalledWith(session.id);
    });

    it('session should be disabled when editing another session', async () => {
        rerender(<Session editingTitle='session2' setEditingTitle={vi.fn()} session={session as SessionInterface} refetch={vi.fn()} isSelected={false}/>);
        const currSession = getByTestId('session');
        fireEvent.click(currSession);
        expect(setSessionFn).not.toBeCalled();
    });
});