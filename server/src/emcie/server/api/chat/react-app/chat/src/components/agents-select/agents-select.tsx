import { ReactElement, useEffect } from 'react';
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import useFetch from '@/hooks/useFetch';

interface Agent {
    id: string;
    name: string;
}

export default function AgentsSelect({value, setSelectedAgent}: {value?: string | undefined, setSelectedAgent: (val: string) => void}): ReactElement {
    const {data} = useFetch<{agents: Agent[]}>('agents');

    useEffect(() => {
        if (!value && data?.agents?.length) setSelectedAgent(data.agents[0].id);
    }, [value, setSelectedAgent, data]);

    return (
        <Select value={value} onValueChange={(val: string) => setSelectedAgent(val)}>
            <SelectTrigger className="w-[180px] border border-solid border-black bg-transparent">
                <SelectValue placeholder="Select an agent" />
            </SelectTrigger>
            <SelectContent>
                <SelectGroup>
                    {data?.agents && data.agents.map(agent => <SelectItem key={agent.id} value={agent.id}>{agent.name}</SelectItem>)}
                </SelectGroup>
            </SelectContent>
        </Select>
    )
}