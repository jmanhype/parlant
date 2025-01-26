import {EventInterface, Log} from '@/utils/interfaces';
import {Bug, Info, Plus, TriangleAlert, X} from 'lucide-react';
import {ReactNode, useEffect, useState} from 'react';
import {getMessageLogs, getMessageLogsWithFilters} from '@/utils/logs';
import {twJoin, twMerge} from 'tailwind-merge';
import clsx from 'clsx';
import HeaderWrapper from '../header-wrapper/header-wrapper';
import {useLocalStorage} from '@/hooks/useLocalStorage';
import LogFilters from '../log-filters/log-filters';
import {useAtom} from 'jotai';
import {sessionIdAtom} from '@/store';
import Markdown from '../markdown/markdown';

interface Filter {
	id: number;
	def: {level?: string; types?: string[]} | null;
}

interface FilterTabsFilterProps {
	filterTabs: Filter[];
	setCurrFilterTabs: React.Dispatch<React.SetStateAction<number | null>>;
	setFilterTabs: React.Dispatch<React.SetStateAction<Filter[] | (() => Filter[])>>;
	currFilterTabs: number | null;
}

const IconMap = {INFO: <Info />, DEBUG: <Bug />, WARNING: <TriangleAlert />};

const Header = ({event, regenerateMessageFn, closeLogs}: {event: EventInterface | null; regenerateMessageFn?: (messageId: string) => void; closeLogs?: VoidFunction}) => {
	const [sessionId] = useAtom(sessionIdAtom);
	return (
		<HeaderWrapper className={twMerge('static')}>
			{event && (
				<div className={twMerge('flex items-center justify-between w-full pe-[20px]')}>
					<div className='flex rounded-[5px] ms-[14px] items-center gap-[7px] hover:bg-[#F5F6F8] py-[13px] px-[10px]' role='button' onClick={() => regenerateMessageFn?.(sessionId as string)}>
						<img src='icons/regenerate-arrow.svg' alt='regenerate' className='block group-hover:hidden h-[15px] w-[15px] min-w-[20px]' />
						<p className='font-medium text-[15px]'>Regenerate Message</p>
					</div>
					<div className='group'>
						<div role='button' className='p-[5px] group-hover:bg-[#ebecf0]' onClick={() => closeLogs?.()}>
							<X height={20} width={20} />
						</div>
					</div>
				</div>
			)}
		</HeaderWrapper>
	);
};

const FilterTabs = ({filterTabs, setCurrFilterTabs, setFilterTabs, currFilterTabs}: FilterTabsFilterProps) => {
	const deleteFilterTab = (id: number) => {
		const filteredTabs = filterTabs.filter((t) => t.id !== id);
		setFilterTabs(filteredTabs);
		if (currFilterTabs === id) setCurrFilterTabs(() => filteredTabs[0]?.id || null);
	};

	const addFilter = () => {
		const val: Filter = {id: Date.now(), def: {level: 'DEBUG', types: []}};
		const allTabs = [...filterTabs, val];
		setFilterTabs(allTabs);
		setCurrFilterTabs(val.id);
	};

	return (
		<div className='flex bg-[#fbfbfb] items-center filter-tabs border-b min-h-[36px] max-h-[36px] overflow-x-auto overflow-y-hidden no-scrollbar'>
			{filterTabs.map((tab: Filter, i: number) => (
				<div
					key={tab.id}
					role='button'
					onClick={() => setCurrFilterTabs(tab.id)}
					className={twJoin('group flex min-h-[36px] max-h-[36px] justify-center items-center ps-[14px] pe-[8px] p-[10px] border-e w-fit', tab.id === currFilterTabs && '!bg-white', i === 0 && 'ps-[24px]')}>
					<div className='flex items-center gap-[8px]'>
						<p className='text-[15px]'>{`filter_${i + 1}`}</p>
						{filterTabs.length > 0 && (
							<X role='button' className={twJoin('size-[18px] group-hover:visible hover:bg-[#656565] hover:text-white rounded-[3px]', tab.id !== currFilterTabs && 'invisible group-hover:visible')} onClick={() => deleteFilterTab(tab.id)} />
						)}
						{/* {filterTabs.length > 0 && <img src='icons/close.svg' alt='close' className='h-[20px]' role='button' height={10} width={10} onClick={() => deleteFilterTab(tab.id)} />} */}
					</div>
				</div>
			))}
			<div className='flex gap-[10px] ms-[6px] items-center rounded-[2px] p-[4px] w-fit sticky right-0 text-[#656565] hover:text-[#151515] hover:bg-[#EBECF0]' role='button' onClick={addFilter}>
				<Plus size={16} />
			</div>
		</div>
	);
};

const UnselectedMessage = () => {
	return (
		<div className='flex flex-col m-auto justify-center items-center max-w-[378px] w-full h-full'>
			<img className='size-[224px] rounded-full' src='emcie-placeholder.svg' alt='' />
			<h2 className='text-[20px] font-medium font-inter text-[#656565] mt-[30px]'>No message has been selected</h2>
			<p className='text-[15px] font-normal font-inter text-[#656565] text-center mt-[10px]'>Please select one of the messages so we can give you more information</p>
		</div>
	);
};

const MessageLogs = ({event, closeLogs, regenerateMessageFn}: {event?: EventInterface | null; closeLogs?: VoidFunction; regenerateMessageFn?: (sessionId: string) => void}): ReactNode => {
	const [filters, setFilters] = useState({});
	const [filterTabs, setFilterTabs] = useLocalStorage<any>('filters', []);
	const [currFilterTabs, setCurrFilterTabs] = useState<number | null>((filterTabs as Filter[])[0]?.id || null);
	const [logs, setLogs] = useState<Log[]>([]);
	const [filteredLogs, setFilteredLogs] = useState<Log[]>([]);

	useEffect(() => {
		if (logs) {
			if (!Object.keys(filters).length) setFilteredLogs(logs);
			else {
				setFilteredLogs(getMessageLogsWithFilters(event?.correlation_id as string, filters as {level: string; types?: string[]; content?: string[]}));
				setFilterTabs((tabFilters: Filter[]) => {
					if (!tabFilters.length) {
						const filter = {id: Date.now(), def: filters};
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

	return (
		<div className={twJoin('w-full h-full overflow-auto flex flex-col justify-start pt-0 pe-0 bg-white')}>
			<Header event={event || null} closeLogs={closeLogs} regenerateMessageFn={regenerateMessageFn} />
			{event && !!logs.length && !!filterTabs?.length && <FilterTabs currFilterTabs={currFilterTabs} filterTabs={filterTabs} setFilterTabs={setFilterTabs} setCurrFilterTabs={setCurrFilterTabs} />}
			{event && !!logs.length && (
				<LogFilters filterId={currFilterTabs || undefined} def={structuredClone(filterTabs.find((t: Filter) => currFilterTabs === t.id)?.def || null)} applyFn={(types, level, content) => setFilters({types, level, content})} />
			)}
			{!event && <UnselectedMessage />}
			{event && !logs.length && <div className='h-full flex justify-center items-center flex-1'>Logs not found</div>}
			{event && !!logs.length && !filteredLogs.length && <div className='h-full flex justify-center items-center flex-1'>No data</div>}
			{event && !!filteredLogs.length && (
				<div className='bg-white p-[14px] pt-0 h-auto overflow-auto flex-1'>
					<div className='rounded-[5px] p-[10px] h-full overflow-auto bg-[#F3F4F8]'>
						{filteredLogs.map((log, i) => (
							<div key={i} className={twJoin('flex items-center gap-[5px] px-[20px] p-[5px] hover:bg-white')}>
								{/* <div className='self-start'>{IconMap[log.level]}</div> */}
								<Markdown className={clsx('max-w-[-webkit-fill-available] pe-[10px]')}>{log?.message}</Markdown>
							</div>
						))}
					</div>
				</div>
			)}
		</div>
	);
};

export default MessageLogs;
