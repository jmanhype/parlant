import { ReactNode } from 'react';
import Tooltip from '../ui/custom/tooltip';
import { useSession } from '../chatbot/chatbot';
import { spaceClick } from '@/utils/methods';
import AgentsList from '../agents-list/agents-list';

export const NEW_SESSION_ID = 'NEW_SESSION';

const ChatHeader = (): ReactNode => {
    const {setAgentId, openDialog} = useSession();

    const createNewSession = () => {
        setAgentId(null);
        openDialog('Select an Agent', <AgentsList/>, '536px', '604px');
     };

    return (
        <div className='h-[70px] min-h-[70px] flex justify-between bg-white border-b-[0.6px] border-b-solid border-muted'>
            <div className='w-[332px] h-[70px] flex items-center justify-between'>
                <div className='flex items-center'>
                    <img src="parlant-bubble-app-logo.svg" alt="logo" height={17.9} width={20.89} className='ms-[24px] me-[6px]'/>
                    <p className='text-[19.4px] font-bold'>Parlant</p>
                </div>
                <div className='group'>
                    <Tooltip value='New Session' side='right'>
                        <div>
                            <img onKeyDown={spaceClick} onClick={createNewSession} tabIndex={1} role='button' src="icons/add.svg" alt="add session" height={28} width={28} className='me-[6px] cursor-pointer group-hover:hidden'/>
                            <img onKeyDown={spaceClick} onClick={createNewSession} tabIndex={1} role='button' src="icons/add-filled.svg" alt="add session" height={28} width={28} className='me-[6px] cursor-pointer hidden group-hover:block'/>
                        </div>
                    </Tooltip>
                </div>
            </div>
        </div>
    );
};

export default ChatHeader;