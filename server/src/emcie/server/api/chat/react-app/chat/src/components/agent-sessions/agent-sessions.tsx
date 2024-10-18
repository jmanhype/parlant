import React, { Dispatch, ReactElement, SetStateAction, useEffect, useRef, useState } from "react";
import useFetch from "@/hooks/useFetch";
import { Button } from "../ui/button";
import { deleteData, patchData } from "@/utils/api";
import { Check, Edit, Trash, X } from "lucide-react";
import { Input } from "../ui/input";

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
    const sessionNameRef = useRef<HTMLInputElement>(null);
    const [refetch, setRefetch] = useState(false);
    const [sessions, setSessions] = useState<Session[]>([]);
    const [isEditingTitle, setIsEditingTitle] = useState({});
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

    const editTitle = async (e: React.MouseEvent, sessionId: string) => {
        e.stopPropagation();
        setIsEditingTitle({[sessionId]: true});
    }

    const saveTitleChange = (e: React.MouseEvent, sessionId: string) => {
        e.stopPropagation();
        if (sessionNameRef?.current?.value) patchData(`sessions/${sessionId}`, {title: sessionNameRef.current.value}).then(() => {setRefetch(!refetch); setIsEditingTitle({});})
    };

    const cancel = (e: React.MouseEvent) => {
        e.stopPropagation();
        setIsEditingTitle({});
    };

    return (
        <div className="flex justify-center pt-4 flex-col gap-4 w-[80%]">
            {sessions.map(session => (
                <div onClick={() => setSession(session.id)} key={session.id} className={"bg-slate-200 border border-solid border-black cursor-pointer p-1 rounded flex items-center gap-4 justify-between ps-4 " + (session.id === sessionId ? '!bg-blue-600 text-white' : '')}>
                    <div>
                        {!isEditingTitle[session.id] && <div>{session.title}</div>}
                        {isEditingTitle[session.id] && <Input ref={sessionNameRef} onClick={e => e.stopPropagation()} autoFocus defaultValue={session.title} className="bg-transparent text-[unset] h-fit p-0 ps-1" onChange={(e: React.ChangeEvent) => editTitle(e, session.id)}/>}
                    </div>
                    <div>
                        {!isEditingTitle[session.id] && <Button title="edit" variant='ghost' className="w-[40px] p-0" onClick={(e: React.MouseEvent) => editTitle(e, session.id)}><Edit/></Button>}
                        {!isEditingTitle[session.id] && <Button variant='ghost' className="w-[40px] p-0" onClick={(e: React.MouseEvent) => deleteSession(e, session.id)}><Trash/></Button>}
                        
                        {isEditingTitle[session.id] && <Button variant='ghost' className="w-[40px] p-0" onClick={cancel}><X/></Button>}
                        {isEditingTitle[session.id] && <Button variant='ghost' className="w-[40px] p-0" onClick={(e: React.MouseEvent) => saveTitleChange(e, session.id)}><Check/></Button>}
                    </div>
                </div>
            ))}
        </div>
    )
}