import { Dispatch, ReactElement, SetStateAction, useState } from "react";
import AgentsSelect from "../agents-select/agents-select";
import AgentSessions from "../agent-sessions/agent-sessions";
import { Button } from "../ui/button";
import { postData } from "@/utils/api";

interface Props {
    setSession: Dispatch<SetStateAction<null>>;
    sessionId: string;
}


export default function Sessions({setSession, sessionId}: Props): ReactElement {
    const [selectedAgent, setSelectedAgent] = useState<string>();

    const createNewSession = () => {
       return postData('sessions?allow_greeting=true', {end_user_id: '1122', agent_id: selectedAgent, title: 'New Conversaion' })
        .then(res => setSession(res.session.id))
    }
    return (
        <div className="flex flex-col items-center h-full overflow-auto">
            <div className="flex justify-center gap-4">
                <AgentsSelect value={selectedAgent} setSelectedAgent={setSelectedAgent}/>
                {selectedAgent && <Button onClick={() => createNewSession()}>+</Button>}
            </div>
            {selectedAgent && <AgentSessions agentId={selectedAgent} sessionId={sessionId} setSession={setSession}/>}
        </div>
    )
}