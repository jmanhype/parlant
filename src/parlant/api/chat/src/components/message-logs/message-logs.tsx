import {EventInterface, Log} from '@/utils/interfaces';
import {Bug, Info, Plus, TriangleAlert} from 'lucide-react';
import {ReactNode, useEffect, useState} from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import styles from '../message/message.module.scss';
import {getMessageLogs, getMessageLogsWithFilters} from '@/utils/logs';
import {twJoin} from 'tailwind-merge';
import clsx from 'clsx';
import HeaderWrapper from '../header-wrapper/header-wrapper';
import {useSession} from '../chatbot/chatbot';
import {useLocalStorage} from '@/hooks/useLocalStorage';
import LogFilters from '../log-filters/log-filters';

const IconMap = {INFO: <Info />, DEBUG: <Bug />, WARNING: <TriangleAlert />};

const MessageLogs = ({
	event,
	closeLogs,
	regenerateMessageFn,
}: {
	event?: EventInterface | null;
	closeLogs?: VoidFunction;
	regenerateMessageFn?: (sessionId: string) => void;
}): ReactNode => {
	const {sessionId} = useSession();
	const [filters, setFilters] = useState({});
	// const [filterTabs, setFilterTabs] = useState(['filter_1']);
	const [filterTabs, setFilterTabs] = useLocalStorage('filters', []);
	const [currFilterTabs, setCurrFilterTabs] = useState(filterTabs[0]);
	const [logs, setLogs] = useState<Log[]>([]);
	const [filteredLogs, setFilteredLogs] = useState<Log[]>([]);

	useEffect(() => {
		if (logs) {
			if (!Object.keys(filters).length) setFilteredLogs(logs);
			else {
				setFilteredLogs(getMessageLogsWithFilters(event?.correlation_id as string, filters));
				setFilterTabs((tabFilters) => {
					if (!tabFilters.length) {
						const filter = {name: 'filter_1', def: filters};
						setCurrFilterTabs(filter);
						return [filter];
					}
					const tab = tabFilters.find((t) => t.name === currFilterTabs?.name);
					if (!tab) return tabFilters;
					tab.def = filters;
					return [...tabFilters];
				});
			}
		}
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [logs, filters]);

	useEffect(() => {
		if (!event && logs.length) {
			setLogs([]);
			setFilteredLogs([]);
		}
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [event]);

	useEffect(() => {
		if (!event?.correlation_id) return;
		setLogs(getMessageLogs(event.correlation_id));
	}, [event?.correlation_id]);

	const deleteFilterTab = (tab: string) => {
		setFilterTabs((tabs) => tabs.filter((t) => t.name !== tab));
		if (currFilterTabs?.name === tab) setCurrFilterTabs(filterTabs[0]);
	};

	const addFilter = () => {
		const val = {name: `filter_${filterTabs.length + 1}`, def: null};
		setFilterTabs((tabs) => [...tabs, val]);
		setCurrFilterTabs(val);
	};

	return (
		<div className={twJoin('w-full h-full overflow-auto flex flex-col justify-start pt-0 pe-0 bg-white')}>
			<HeaderWrapper>
				{event && (
					<div className='flex items-center justify-between w-full pe-[30px]'>
						<div
							className='flex ms-[14px] items-center gap-[7px] hover:bg-[#F5F6F8] p-[10px]'
							role='button'
							onClick={() => regenerateMessageFn?.(sessionId as string)}>
							<img src='icons/regenerate-arrow.svg' alt='regenerate' className='block group-hover:hidden h-[15px] w-[15px] min-w-[20px]' />
							<p className='font-medium text-[15px]'>Regenerate Message</p>
						</div>
						<div className='group'>
							<img
								src='icons/close-logs.svg'
								alt='close'
								role='button'
								className='group-hover:hidden'
								height={30}
								width={30}
								onClick={() => closeLogs?.()}
							/>
							<img
								src='icons/close-logs-hover.svg'
								alt='close'
								role='button'
								className='hidden group-hover:block'
								height={30}
								width={30}
								onClick={() => closeLogs?.()}
							/>
						</div>
					</div>
				)}
			</HeaderWrapper>
			{event && !!logs.length && !!filterTabs?.length && (
				<div className='flex bg-[#FBFBFB] items-center filter-tabs border-b min-h-[45px] overflow-x-auto overflow-y-hidden no-scrollbar'>
					{filterTabs.map((tab) => (
						<div
							key={tab.name}
							role='button'
							onClick={() => setCurrFilterTabs(tab)}
							className={twJoin(
								'flex min-w-[125px] justify-center max-w-[125px] bg-white gap-[10px] items-center p-[10px] border-e w-fit',
								tab.name === currFilterTabs?.name && 'font-bold'
							)}>
							<p className='text-[#656565] text[15px]'>{tab.name}</p>
							{filterTabs.length > 0 && (
								<img
									src='icons/close.svg'
									alt='close'
									className='h-[20px]'
									role='button'
									height={10}
									width={10}
									onClick={() => deleteFilterTab(tab.name)}
								/>
							)}
						</div>
					))}
					<div className='flex gap-[10px] items-center p-[10px] w-fit sticky bg-[#FBFBFB] right-0'>
						<Plus role='button' onClick={addFilter} />
					</div>
				</div>
			)}
			{event && !!logs.length && (
				<LogFilters filterName={currFilterTabs?.name} def={currFilterTabs?.def} applyFn={(types, level) => setFilters({types, level})} />
			)}
			{!event && (
				<div className='flex flex-col m-auto justify-center items-center max-w-[378px] w-full h-full'>
					<img className='size-[224px] rounded-full' src='emcie-placeholder.svg' alt='' />
					<h2 className='text-[20px] font-medium font-inter text-[#656565] mt-[30px]'>No message has been selected</h2>
					<p className='text-[15px] font-normal font-inter text-[#656565] text-center mt-[10px]'>
						Please select one of the messages so we can give you more information
					</p>
				</div>
			)}
			{event && !logs.length && <div className='h-full flex justify-center items-center'>Logs not found</div>}
			{event && !!logs.length && !filteredLogs.length && <div className='h-full flex justify-center items-center'>No data</div>}
			{event && !!filteredLogs.length && (
				<div>
					{filteredLogs.map((log, i) => (
						<div key={i} className={twJoin('flex items-center gap-[5px] p-[5px] border-t')}>
							<div className='self-start'>{IconMap[log.level]}</div>
							<Markdown remarkPlugins={[remarkGfm, remarkBreaks]} className={clsx(styles.markdown, 'max-w-[-webkit-fill-available] pe-[10px]')}>
								{log?.message}
							</Markdown>
							{/* <div>{log.message}</div> */}
						</div>
					))}
				</div>
			)}
		</div>
	);
};

export default MessageLogs;
