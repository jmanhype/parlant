import React, { Dispatch, ReactElement, SetStateAction, useEffect, useState } from "react";
import useFetch from "@/hooks/useFetch";
import { Button } from "../ui/button";
import { deleteData } from "@/utils/api";
import { Trash } from "lucide-react";

interface Props {
    agentId: string | undefined;
    setSession: Dispatch<SetStateAction<null>>;
    sessionId: string;
}

interface Session {
    id: string;
    title: string;
    end_user_id: string;
}

export default function AgentSessions({agentId, setSession, sessionId}: Props): ReactElement {
    const [refetch, setRefetch] = useState(false);
    const [sessions, setSessions] = useState<Session[]>([]);
    const {data} = useFetch<{sessions: Session[]}>('sessions/', {agent_id: agentId}, [refetch]);

    useEffect(() => {
        if (data?.sessions) setSessions(data?.sessions);
        if (sessionId && !sessions?.some(s => s.id === sessionId)) setRefetch(!refetch);
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [sessionId, data]);

    const deleteSession = async (e: React.MouseEvent, sessionId: string) => {
        e.stopPropagation();
        return deleteData(`sessions/${sessionId}`).then(() => {setRefetch(!refetch); setSession(null)})
    }

    return (
        <div className="flex justify-center pt-4 flex-col gap-4 w-[80%]">
            {sessions.map(session => (
                <div onClick={() => setSession(session.id)} key={session.id} className={"bg-slate-200 border border-solid border-black cursor-pointer p-1 rounded flex items-center gap-4 justify-between ps-4 " + (session.id === sessionId ? 'bg-blue-600 text-white' : '')}>
                    <div>
                        <div>{session.title}</div>
                    </div>
                    <Button variant='ghost' onClick={(e: React.MouseEvent) => deleteSession(e, session.id)}>
                        <Trash/>
                    </Button>
                </div>
            ))}
        </div>
    )
}