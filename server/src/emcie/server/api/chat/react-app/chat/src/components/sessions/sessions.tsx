import { Dispatch, ReactElement, SetStateAction, useState } from "react";
import AgentsSelect from "../agents-select/agents-select";
import AgentSessions from "../agent-sessions/agent-sessions";
import { Button } from "../ui/button";
import { postData } from "@/utils/api";

interface Props {
    setSession: Dispatch<SetStateAction<null>>;
    sessionId: string | null;
}


export default function Sessions({setSession, sessionId}: Props): ReactElement {
    const [selectedAgent, setSelectedAgent] = useState<string>();

    const createNewSession = () => {
       return postData('sessions?allow_greeting=true', {end_user_id: '1122', agent_id: selectedAgent, title: 'New Conversation' })
        .then(res => setSession(res.session.id))
    }
    return (
        <div className="flex flex-col items-center h-full overflow-auto pt-4">
            <div className="flex justify-between gap-4 w-[80%]">
                <AgentsSelect value={selectedAgent} setSelectedAgent={setSelectedAgent}/>
                <Button disabled={!selectedAgent} onClick={() => createNewSession()}>+</Button>
            </div>
            {selectedAgent && <AgentSessions agentId={selectedAgent} sessionId={sessionId} setSession={setSession}/>}
        </div>
    )
}