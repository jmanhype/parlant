import { ReactElement } from "react";
import useFetch from "../../hooks/useFetch";
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue } from "../ui/select";

export default function Sessions(): ReactElement {
    const {data, error, loading} = useFetch('agents');

    return (
        <div className="flex justify-center pt-4">
            <Select>
                <SelectTrigger className="w-[180px]">
                    <SelectValue placeholder="Select an agent" />
                </SelectTrigger>
                <SelectContent>
                    <SelectGroup>
                        {data?.agents && data.agents.map(agent => <SelectItem key={agent.id} value={agent.id}>{agent.name}</SelectItem>)}
                    </SelectGroup>
                </SelectContent>
            </Select>
        </div>
    )
}