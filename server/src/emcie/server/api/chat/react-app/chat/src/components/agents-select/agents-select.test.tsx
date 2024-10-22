import { cleanup, fireEvent, render } from '@testing-library/react';
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
}));

describe(AgentsSelect, () => {
    afterEach(() => cleanup());
    
    it('component should be rendered', () => {
        const {getByRole} = render(<AgentsSelect setSelectedAgent={vi.fn()}/>);
        const selectBox = getByRole('combobox');
        expect(selectBox).toBeInTheDocument();
    });

    it('selects the first agent if no value is provided', () => {
        const mockSetSelectedAgent = vi.fn();
        render(<AgentsSelect setSelectedAgent={mockSetSelectedAgent}/>);

        expect(mockSetSelectedAgent).toHaveBeenCalledWith('agent1');
    });

    it('does not select the first agent if no value is provided', () => {
        const mockSetSelectedAgent = vi.fn();
        render(<AgentsSelect value='agent1' setSelectedAgent={mockSetSelectedAgent}/>);

        expect(mockSetSelectedAgent).not.toHaveBeenCalled();
    });
    
    it('2 options should be available as options', () =>{
        const { getByText, getByRole } = render(<AgentsSelect setSelectedAgent={vi.fn()}/>);
        const select = getByRole('combobox');
        fireEvent.click(select);

        expect(getByText('Agent One')).toBeInTheDocument();
        expect(getByText('Agent Two')).toBeInTheDocument();
    });
    
    it('calls setSelectedAgent when an agent is selected', () =>{
        const mockSetSelectedAgent = vi.fn();
        const { getByText, getByRole } = render(<AgentsSelect setSelectedAgent={mockSetSelectedAgent}/>);
    
        vi.clearAllMocks();

        fireEvent.click(getByRole('combobox'));
        fireEvent.click(getByText('Agent One'));

        expect(mockSetSelectedAgent).toHaveBeenCalledWith('agent1');
    });

    it('agent1 should be selected', async () => {
        const {getByRole} = render(<AgentsSelect value='agent1' setSelectedAgent={vi.fn()}/>);
        const selectBox = getByRole('combobox');
        expect(selectBox).toHaveTextContent('Agent One');
    });
});
