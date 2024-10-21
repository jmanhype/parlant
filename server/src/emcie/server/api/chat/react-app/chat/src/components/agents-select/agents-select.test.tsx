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

    it('component should be rendered', () => {
        const {getByRole} = render(<AgentsSelect setSelectedAgent={vi.fn()}/>);
        const selectBox = getByRole('combobox');
        expect(selectBox).toBeInTheDocument();
    });

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
