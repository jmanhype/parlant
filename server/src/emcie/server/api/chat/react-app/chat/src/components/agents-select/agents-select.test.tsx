import { render } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import AgentsSelect from './agents-select.tsx';
import '@testing-library/jest-dom/vitest';

vi.mock('@/hooks/useFetch', () => ({
    default: () => ({
        data: {
            agents: [
                { id: 'agent1', name: 'Agent One' },
                { id: 'agent2', name: 'Agent Two' }
            ],
        },
    }),
}))

describe('Agent Select Component', () => {
    it('select-box should be rendered', () => {
        const {getByRole} = render(<AgentsSelect setSelectedAgent={vi.fn()}/>);
        const selectBox = getByRole('combobox');
        expect(selectBox).toBeInTheDocument();
    });

    // it('should have 2 options', async () => {
    //     const {getByRole} = render(<AgentsSelect setSelectedAgent={vi.fn()}/>);
    //     const selectBox = getByRole('combobox');
    //     fireEvent.click(selectBox);
    //     const selectOptions = await waitFor(() => screen.getAllByRole('option'));

    //     expect(selectOptions).toHaveLength(2);
    // });

    it('none should be selected', async () => {
        const {getByRole} = render(<AgentsSelect setSelectedAgent={vi.fn()}/>);
        const selectBox = getByRole('combobox');
        expect(selectBox).toHaveTextContent('Select an agent');
    });

    it('agent1 should be selected', async () => {
        const {getByRole} = render(<AgentsSelect value='agent1' setSelectedAgent={vi.fn()}/>);
        const selectBox = getByRole('combobox');
        expect(selectBox).toHaveTextContent('Agent One');
    });
});
