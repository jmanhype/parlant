import { ReactElement, useState } from "react";
import AgentsSelect from "../agents-select/agents-select";
import AgentSessions from "../agent-sessions/agent-sessions";

export default function Sessions(): ReactElement {
    const [selectedAgent, setSelectedAgent] = useState<string>();

    return (
        <div className="flex flex-col items-center pt-4">
            <AgentsSelect value={selectedAgent} setSelectedAgent={setSelectedAgent}/>
            <AgentSessions agentId={selectedAgent}/>
        </div>
    )
}