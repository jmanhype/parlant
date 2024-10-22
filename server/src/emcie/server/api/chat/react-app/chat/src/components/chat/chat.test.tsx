import { describe, expect, it, vi } from 'vitest';
import { act, fireEvent, MatcherOptions, render } from '@testing-library/react';
import { Matcher } from 'vite';
import Chat from './chat';
import { postData } from '@/utils/api';


vi.mock('@/utils/api', () => ({
    postData: vi.fn(() => Promise.resolve())
}));

describe(Chat, () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    let getByRole: (id: Matcher, options?: MatcherOptions | undefined) => HTMLElement;
    
    beforeEach(async () => {
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

    it('submit button should be enabled when typing', async () => {
        const submitBtn = getByRole('button');
        const textarea = getByRole('textbox');
        await act(async () => fireEvent.change(textarea, {target: {value: 'hello'}}));
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