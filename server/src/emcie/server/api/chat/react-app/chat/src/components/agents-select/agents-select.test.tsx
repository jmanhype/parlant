import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import AgentsSelect from './agents-select.tsx';
import '@testing-library/jest-dom/vitest';
import { NEW_SESSION_ID } from '../sessions/sessions.tsx';

vi.mock('@/hooks/useFetch', () => ({
    default: () => ({
        data: {
            agents: [
                { id: 'agent1', name: 'Agent One' },
                { id: 'agent2', name: 'Agent Two' }
            ],
        },
    }),
}));

vi.mock('../chatbot/chatbot', () => ({
    useSession: () => ({
        sessionId: NEW_SESSION_ID,
        agentId: '123'
    }),
}));

describe(AgentsSelect, () => {
    beforeEach(() => vi.clearAllMocks());
    afterEach(() => cleanup());
    
    it('component should be rendered', () => {
        const {getByRole} = render(<AgentsSelect/>);
        const selectBox = getByRole('combobox');
        expect(selectBox).toBeInTheDocument();
    });

    it('2 options should be available as options', async () => {
        const { getByText, getByRole } = render(<AgentsSelect/>);
        const select = getByRole('combobox');
        fireEvent.click(select);

        expect(getByText('Agent One')).toBeInTheDocument();
        expect(getByText('Agent Two')).toBeInTheDocument();
    });

    it('agent1 should be selected', async () => {
        const {getByRole} = render(<AgentsSelect value='agent1'/>);
        const selectBox = getByRole('combobox');
        expect(selectBox).toHaveTextContent('Agent One');
    });
});
