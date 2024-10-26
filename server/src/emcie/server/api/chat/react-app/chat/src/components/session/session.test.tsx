import { cleanup, fireEvent, MatcherOptions, render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { Matcher } from 'vite';
import Session from './session';
import { deleteData } from '@/utils/api';
import { SessionInterface } from '@/utils/interfaces';
import userEvent from '@testing-library/user-event';

const session: SessionInterface | null = { id: 'session1', title: 'Session One', end_user_id: '', agentId: '', creation_utc: new Date().toLocaleString()};

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
        const utils = render(<Session session={session as SessionInterface} refetch={vi.fn()} isSelected={true}/>);
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
        rerender(<Session session={session as SessionInterface} refetch={vi.fn()} isSelected={false}/>);
        const moreBtn = getByTestId('menu-button');
        await userEvent.click(moreBtn);
        const deleteBtn = getByTestId('delete');
        await fireEvent.click(deleteBtn);
        expect(setSessionFn).not.toBeCalled();
    });

    it('text field opened when "edit" button is clicked', async () => {
        const moreBtn = getByTestId('menu-button');
        await userEvent.click(moreBtn);
        const editBtn = getByTestId('rename');
        fireEvent.click(editBtn);
        const textfields = container.querySelector('input');
        expect(textfields).toBeInTheDocument();
    });

    it('text field closed when "cancel edit" button is clicked', async () => {
        const moreBtn = getByTestId('menu-button');
        await userEvent.click(moreBtn);
        const editBtn = getByTestId('rename');
        fireEvent.click(editBtn);
        const textfields = container.querySelector('input');
        expect(textfields).toBeInTheDocument();
        const cancelBtn = getByTestId('cancel');
        fireEvent.click(cancelBtn);
        expect(textfields).not.toBeInTheDocument();
    });
});