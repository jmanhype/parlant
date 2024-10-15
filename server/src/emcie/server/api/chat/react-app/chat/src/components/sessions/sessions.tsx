import { Dispatch, ReactElement, SetStateAction, useState } from "react";
import AgentsSelect from "../agents-select/agents-select";
import AgentSessions from "../agent-sessions/agent-sessions";
import { Button } from "../ui/button";
import { postData } from "@/utils/api";

interface Props {
    setSession: Dispatch<SetStateAction<null>>
}

const createNewSession = (agent_id: string) => {
    postData('sessions?allow_greeting=true', {end_user_id: '1122', agent_id, title: 'New Conversaion' })
}

export default function Sessions({setSession}: Props): ReactElement {
    const [selectedAgent, setSelectedAgent] = useState<string>();

    return (
        <div className="flex flex-col items-center pt-4">
            <div className="flex justify-center gap-4">
                <AgentsSelect value={selectedAgent} setSelectedAgent={setSelectedAgent}/>
                {selectedAgent && <Button onClick={() => createNewSession(selectedAgent)}>+</Button>}
            </div>
            {selectedAgent && <AgentSessions agentId={selectedAgent} setSession={setSession}/>}
        </div>
    )
}