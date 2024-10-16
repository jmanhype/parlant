import { Dispatch, ReactElement, SetStateAction, useState } from "react";
import useFetch from "@/hooks/useFetch";
import { Button } from "../ui/button";
import { deleteData } from "@/utils/api";

interface Props {
    agentId: string | undefined;
    setSession: Dispatch<SetStateAction<null>>;
    sessionId: string;
}

export default function AgentSessions({agentId, setSession, sessionId}: Props): ReactElement {
    const [refetch, setRefetch] = useState(false);
    const results = useFetch('sessions/', {agent_id: agentId}, [refetch]);

    const deleteSession = async (e: MouseEvent, sessionId: string) => {
        e.stopPropagation();
        return deleteData(`sessions/${sessionId}`).then(() => setRefetch(!refetch))
    }

    return (
        <div className="flex justify-center pt-4 flex-col gap-4">
            {results?.data?.sessions && results.data.sessions.map(session => (
                <div onClick={() => setSession(session.id)} key={session.id} className={"bg-slate-200 border border-solid border-black cursor-pointer p-1 rounded flex items-center gap-4 justify-between " + (session.id === sessionId ? 'bg-red-200' : '')}>
                    <div>
                        <div>{session.title}</div>
                        <div>{session.end_usser_id}</div>
                    </div>
                    <Button onClick={(e: MouseEvent) => deleteSession(e, session.id)}>Delete</Button>
                </div>
            ))}
        </div>
    )
}