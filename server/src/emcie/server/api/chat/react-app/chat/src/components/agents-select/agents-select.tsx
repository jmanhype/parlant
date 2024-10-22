import { ReactElement, useEffect } from 'react';
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import useFetch from '@/hooks/useFetch';
import { AgentInterface } from '@/utils/interfaces';

export default function AgentsSelect({value, setSelectedAgent}: {value?: string | undefined, setSelectedAgent: (val: string) => void}): ReactElement {
    const {data} = useFetch<{agents: AgentInterface[]}>('agents');

    useEffect(() => {
        if (!value && data?.agents?.length) setSelectedAgent(data.agents[0].id);
    }, [value, setSelectedAgent, data]);

    return (
        <Select value={value} onValueChange={(val: string) => setSelectedAgent(val)}>
            <SelectTrigger style={{boxShadow: 'none'}} className="w-full h-full border-none rounded-none text-[16px] text-[#151515] font-medium">
                <div className='flex flex-col'>
                    <SelectValue placeholder="Select an agent" />
                </div>
            </SelectTrigger>
            <SelectContent>
                <SelectGroup>
                    {data?.agents && data.agents.map(agent =>
                        <SelectItem className='text-[16px] text-[#151515] font-medium h-[69px] font-ubuntu-sans' key={agent.id} value={agent.id}>
                            {agent.name}
                            {value && <p className='font-light text-[14px] text-[#A9A9A9] font-inter'>(id={value})</p>}
                        </SelectItem>)
                    }
                </SelectGroup>
            </SelectContent>
        </Select>
    );
}