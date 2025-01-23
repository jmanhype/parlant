import {createContext, lazy, ReactElement, ReactNode, Suspense, useContext, useEffect, useState} from 'react';
import Sessions from '../sessions/sessions';
import ErrorBoundary from '../error-boundary/error-boundary';
import ChatHeader from '../chat-header/chat-header';
import {Dimensions, useDialog} from '@/hooks/useDialog';
import {Helmet} from 'react-helmet';
import {NEW_SESSION_ID} from '../agents-list/agent-list';
import HeaderWrapper from '../header-wrapper/header-wrapper';
import {useAtom} from 'jotai';
import {closeDialogAtom, sessionIdAtom, sessionsAtom} from '@/store';

interface SessionContext {
	openDialog: (title: string | null, content: ReactNode, dimensions: Dimensions, dialogClosed?: (() => void) | null) => void;
	closeDialog: () => void;
}

export const SessionProvider = createContext<SessionContext>({
	openDialog: () => null,
	closeDialog: () => null,
});

// eslint-disable-next-line react-refresh/only-export-components
export const useSession = () => useContext(SessionProvider);

export default function Chatbot(): ReactElement {
	const Chat = lazy(() => import('../chat/chat'));
	const [sessionName, setSessionName] = useState<string | null>('');
	const {openDialog, DialogComponent, closeDialog} = useDialog();
	const [sessionId] = useAtom(sessionIdAtom);
	const [sessions] = useAtom(sessionsAtom);
	const [, setCloseDialog] = useAtom(closeDialogAtom);

	useEffect(() => {
		if (sessionId) {
			if (sessionId === NEW_SESSION_ID) setSessionName('Parlant | New Session');
			else {
				const sessionTitle = sessions?.find((session) => session.id === sessionId)?.title;
				if (sessionTitle) setSessionName(`Parlant | ${sessionTitle}`);
			}
		} else setSessionName('Parlant');
	}, [sessionId, sessions]);

	useEffect(() => {
		if (closeDialog) setCloseDialog(closeDialog);
	}, []);

	const provideObj = {
		openDialog,
		closeDialog,
	};

	return (
		<ErrorBoundary>
			<SessionProvider.Provider value={provideObj}>
				<Helmet defaultTitle={`${sessionName}`} />
				<div data-testid='chatbot' className='main bg-main h-screen flex flex-col'>
					<div className='hidden max-mobile:block'>
						<ChatHeader />
					</div>
					<div className='flex justify-between flex-1 w-full overflow-auto flex-row'>
						<div className='bg-white h-full pb-4 border-solid w-[332px] max-mobile:hidden z-[11] border-e'>
							<ChatHeader />
							<Sessions />
						</div>
						<div className='h-full w-[calc(100vw-332px)] max-w-[calc(100vw-332px)] max-[750px]:max-w-full max-[750px]:w-full '>
							{sessionId ? (
								<Suspense>
									<Chat />
								</Suspense>
							) : (
								<HeaderWrapper />
							)}
						</div>
					</div>
				</div>
			</SessionProvider.Provider>
			<DialogComponent />
		</ErrorBoundary>
	);
}
