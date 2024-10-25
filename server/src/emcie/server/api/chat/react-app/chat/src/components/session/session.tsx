import { ReactElement, useEffect, useRef, useState } from 'react';
import { Input } from '../ui/input';
import Tooltip from '../ui/custom/tooltip';
import { Button } from '../ui/button';
import { deleteData, patchData } from '@/utils/api';
import { toast } from 'sonner';
import { Check, X } from 'lucide-react';
import { useSession } from '../chatbot/chatbot';
import { SessionInterface } from '@/utils/interfaces';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '../ui/dropdown-menu';

interface Props {
    session: SessionInterface;
    isSelected: boolean;
    refetch: () => void;
}

export default function Session({session, isSelected, refetch}: Props): ReactElement {
    const sessionNameRef = useRef<HTMLInputElement>(null);
    const [isEditingTitle, setIsEditingTitle] = useState<boolean>(false);
    const {setSessionId, setAgentId, setNewSession} = useSession();

    useEffect(() => {
        if (!isSelected) return;

        if (session.id === 'NEW_SESSION' && !session.agentId) setAgentId(null);
        else setAgentId('Mr0uvCuu6g');
    }, [isSelected, setAgentId, session.id, session.agentId]);

    const deleteSession = async (e: React.MouseEvent) => {
        e.stopPropagation();
        if (session.id === 'NEW_SESSION') {
            setNewSession(null);
            setSessionId(null);
            setAgentId(null);
            return;
        }
        return deleteData(`sessions/${session.id}`).then(() => {
            refetch();
            if (isSelected) setSessionId(null);
            toast.success(`Session "${session.title}" deleted successfully`, {closeButton: true});
        }).catch(() => {
            toast.error('Something went wrong');
        });
    };

    const editTitle = async (e: React.MouseEvent) => {
        e.stopPropagation();
        setIsEditingTitle(true);
        setTimeout(() => sessionNameRef?.current?.select(), 0);
    };

    const saveTitleChange = (e: React.MouseEvent | React.KeyboardEvent) => {
        e.stopPropagation();
        const title = sessionNameRef?.current?.value;
        if (title) {
            if (session.id === 'NEW_SESSION') {
                setIsEditingTitle(false);
                setNewSession(session => session ? {...session, title} : session);
                toast.success('title changed successfully', {closeButton: true});
                return;
            }
            patchData(`sessions/${session.id}`, {title})
            .then(() => {
                refetch();
                toast.success('title changed successfully', {closeButton: true});
            }).catch(() => {
                toast.error('Something went wrong');
            });
        }
    };

    const cancel = (e: React.MouseEvent) => {
        e.stopPropagation();
        setIsEditingTitle(false);
    };

    const onInputKeyUp = (e: React.KeyboardEvent) =>{
        if (e.key === 'Enter') saveTitleChange(e);
    };

    return (
        <div data-testid="session"
            role="button"
            tabIndex={0}
            onKeyDown={e => e.key === ' ' && (e.target as HTMLElement).click()}
            onClick={() => setSessionId(session.id)} key={session.id}
            className={'bg-white duration-500 transition-none text-[14px] font-medium border-b-[0.6px] border-b-solid border-[#EBECF0] cursor-pointer p-1 flex items-center gap-4 justify-between ps-4 min-h-[80px] h-[80px] ml-4 mr-4 lg:ml-0 lg:mr-0 hover:bg-[#FBFBFB] ' + (isSelected ? '!bg-[#FAF9FF]' : '')}>
            <div className="flex-1 whitespace-nowrap overflow-hidden">
                {!isEditingTitle &&
                    <div className="overflow-hidden overflow-ellipsis">
                        {session.title}
                        <small className='block text-[12px] text-[#A9A9A9] font-light mt-[4px]'>
                            {new Date(session.creation_utc).toLocaleString()}
                        </small>
                    </div>
                }
                {isEditingTitle && <Input data-testid='sessionTitle' ref={sessionNameRef} onKeyUp={onInputKeyUp} onClick={e => e.stopPropagation()} autoFocus defaultValue={session.title} style={{boxShadow: 'none'}} className="bg-[#e2e8f0] text-foreground h-fit p-1 border border-solid border-black"/>}
            </div>
            <div>
                {!isEditingTitle && 
                <DropdownMenu>
                    <DropdownMenuTrigger tabIndex={-1}>
                        <div role='button' className='rounded-full py-2 px-4' onClick={e => e.stopPropagation()}>
                            <img src='/icons/more.svg' height={14} width={14}/>
                        </div>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent>
                        <DropdownMenuItem onClick={editTitle} className='gap-0 font-medium text-[14px] font-ubuntu-sans'>
                            <img src="icons/rename.svg" height={16} width={18} className='me-[8px]' alt="" />
                            Rename
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={deleteSession} className='gap-0 font-medium text-[14px] font-ubuntu-sans'>
                            <img src="icons/delete.svg" height={16} width={18} className='me-[8px]' alt="" />
                            Delete
                        </DropdownMenuItem>
                    </DropdownMenuContent>
                </DropdownMenu>}
                
                {isEditingTitle && <Tooltip value='Cancel'><Button data-testid="cancel" variant='ghost' className="w-[40px] p-0" onClick={cancel}><X/></Button></Tooltip>}
                {isEditingTitle && <Tooltip value='Save'><Button variant='ghost' className="w-[40px] p-0" onClick={saveTitleChange}><Check/></Button></Tooltip>}
            </div>
        </div>
    );
}