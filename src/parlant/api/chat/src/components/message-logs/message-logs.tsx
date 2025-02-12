/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable react-hooks/exhaustive-deps */
import {EventInterface, Log} from '@/utils/interfaces';
import React, {ReactNode, useEffect, useRef, useState} from 'react';
import {getMessageLogs, getMessageLogsWithFilters} from '@/utils/logs';
import {twJoin, twMerge} from 'tailwind-merge';
import clsx from 'clsx';
import {useLocalStorage} from '@/hooks/useLocalStorage';
import LogFilters, {Level, Type} from '../log-filters/log-filters';
import MessageFragments from '../message-fragments/message-fragments';
import EmptyState from './empty-state';
import FilterTabs from './filter-tabs';
import MessageLogsHeader from './message-logs-header';
import MessageLog from './message-log';

interface DefInterface {
	level?: Level;
	types?: Type[];
	content?: string[];
}

interface Filter {
	id: number;
	name: string;
	def: DefInterface | null;
}

const MessageError = ({event}: {event: EventInterface}) => {
	return (
		<div className='h-[300px] p-[20px] bg-[#ebecf0] text-[13px] text-[#ef5350] z-10'>
			<pre className={clsx('p-[10px] max-w-[-webkit-fill-available] pe-[10px] text-wrap break-words bg-white rounded-[8px] h-full overflow-auto')}>{event?.error}</pre>
		</div>
	);
};

const MessageLogs = ({
	event,
	closeLogs,
	regenerateMessageFn,
	resendMessageFn,
}: {
	event?: EventInterface | null;
	closeLogs?: VoidFunction;
	regenerateMessageFn?: (sessionId: string) => void;
	resendMessageFn?: (sessionId: string) => void;
}): ReactNode => {
	const [filters, setFilters] = useState({});
	const [filterTabs, setFilterTabs] = useLocalStorage<Filter[]>('filters', []);
	const [currFilterTabs, setCurrFilterTabs] = useState<number | null>((filterTabs as Filter[])[0]?.id || null);
	const [logs, setLogs] = useState<Log[] | null>(null);
	const [filteredLogs, setFilteredLogs] = useState<Log[]>([]);
	const messagesRef = useRef<HTMLDivElement | null>(null);

	useEffect(() => {
		if (logs) {
			if (!Object.keys(filters).length) setFilteredLogs(logs);
			else {
				setFilteredLogs(getMessageLogsWithFilters(event?.correlation_id as string, filters as {level: string; types?: string[]; content?: string[]}));
				(setFilterTabs as React.Dispatch<React.SetStateAction<Filter[]>>)((tabFilters: Filter[]) => {
					if (!tabFilters.length) {
						const filter = {id: Date.now(), def: filters, name: 'Logs'};
						setCurrFilterTabs(filter.id);
						return [filter];
					}
					const tab = tabFilters.find((t) => t.id === currFilterTabs);
					if (!tab) return tabFilters;
					tab.def = filters;
					return [...tabFilters];
				});
			}
		}
	}, [logs, filters]);

	useEffect(() => {
		if (!event && logs) {
			setLogs(null);
			setFilteredLogs([]);
		}
	}, [event]);

	useEffect(() => {
		if (!event?.correlation_id) return;
		setLogs(getMessageLogs(event.correlation_id));
	}, [event?.correlation_id]);

	const shouldRenderTabs = event && !!logs?.length && !!filterTabs?.length;
	const fragmentEntries = Object.entries(event?.data?.fragments || {}).map(([id, value]) => ({id, value}));
	const isError = event?.serverStatus === 'error';

	return (
		<div className={twJoin('w-full h-full overflow-auto flex flex-col justify-start pt-0 pe-0 bg-[#FBFBFB]')}>
			<MessageLogsHeader
				event={event || null}
				closeLogs={closeLogs}
				resendMessageFn={resendMessageFn}
				regenerateMessageFn={regenerateMessageFn}
				className={twJoin(event && logs && !logs?.length && 'bg-white', Object.keys(filters).length ? 'border-[#DBDCE0]' : '')}
			/>
			{isError && <MessageError event={event} />}
			{!!fragmentEntries.length && <MessageFragments fragments={fragmentEntries} className={twJoin(shouldRenderTabs && 'border-b border-[#dbdce0]')} />}
			{shouldRenderTabs && <FilterTabs setFilters={setFilters as any} currFilterTabs={currFilterTabs} filterTabs={filterTabs as Filter[]} setFilterTabs={setFilterTabs as any} setCurrFilterTabs={setCurrFilterTabs} />}
			{event && (
				<LogFilters
					className={twMerge(!filteredLogs?.length && '', !logs?.length && 'absolute')}
					filterId={currFilterTabs || undefined}
					def={structuredClone((filterTabs as Filter[]).find((t: Filter) => currFilterTabs === t.id)?.def || null)}
					applyFn={(types, level, content) => setFilters({types, level, content})}
				/>
			)}
			{!event && <EmptyState title='Feeling curious?' subTitle='Select a message for additional actions and information about its process.' wrapperClassName='bg-[#f5f6f8]' />}
			{event && logs && !logs?.length && (
				<EmptyState title='Whoopsie!' subTitle="The logs for this message weren't found in cache. Try regenerating it to get fresh logs." wrapperClassName='bg-[#f5f6f8]' className={twJoin(isError && 'translate-y-[0px]')} />
			)}
			{event && !!logs?.length && !filteredLogs.length && <EmptyState title='No logs for the current filters' wrapperClassName='bg-[#ebecf0]' className={twJoin(isError && 'translate-y-[0px]')} />}
			{event && !!filteredLogs.length && (
				<div className='bg-[#EBECF0] p-[14px] pt-0 h-auto overflow-auto flex-1'>
					<div ref={messagesRef} className='rounded-[8px] border-[10px] border-white h-full overflow-auto bg-white fixed-scroll'>
						{filteredLogs.map((log, i) => (
							<MessageLog key={i} log={log} />
						))}
					</div>
				</div>
			)}
		</div>
	);
};

export default MessageLogs;
