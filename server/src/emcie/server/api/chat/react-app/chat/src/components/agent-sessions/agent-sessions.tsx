import { Dispatch, ReactElement, SetStateAction, useEffect, useState } from "react";
import useFetch from "@/hooks/useFetch";
import { Button } from "../ui/button";
import { deleteData } from "@/utils/api";
import { Trash } from "lucide-react";

interface Props {
    agentId: string | undefined;
    setSession: Dispatch<SetStateAction<null>>;
    sessionId: string;
}

export default function AgentSessions({agentId, setSession, sessionId}: Props): ReactElement {
    const [refetch, setRefetch] = useState(false);
    const [sessions, setSessions] = useState([]);
    const results = useFetch('sessions/', {agent_id: agentId}, [refetch]);

    useEffect(() => {
        if (results?.data?.sessions) setSessions(results?.data?.sessions);
        if (sessionId && !sessions?.some(s => s.id === sessionId)) setRefetch(!refetch);
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [sessionId, results]);

    const deleteSession = async (e: MouseEvent, sessionId: string) => {
        e.stopPropagation();
        return deleteData(`sessions/${sessionId}`).then(() => setRefetch(!refetch))
    }

    return (
        <div className="flex justify-center pt-4 flex-col gap-4">
            {sessions.map(session => (
                <div onClick={() => setSession(session.id)} key={session.id} className={"bg-slate-200 border border-solid border-black cursor-pointer p-1 rounded flex items-center gap-4 justify-between " + (session.id === sessionId ? 'bg-red-200' : '')}>
                    <div>
                        <div>{session.title}</div>
                        <div>{session.end_usser_id}</div>
                    </div>
                    <Button variant='ghost' onClick={(e: MouseEvent) => deleteSession(e, session.id)}>
                        <Trash/>
                    </Button>
                </div>
            ))}
        </div>
    )
}