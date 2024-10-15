import { ReactElement } from "react";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "../ui/select";
import useFetch from "@/hooks/useFetch";


export default function AgentsSelect({value, setSelectedAgent}: {value: string | undefined, setSelectedAgent: (val: string) => void}): ReactElement {
    const {data, error, loading} = useFetch('agents');
    return (
        <Select value={value} onValueChange={(val: string) => setSelectedAgent(val)}>
            <SelectTrigger className="w-[180px]">
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