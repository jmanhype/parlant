import {memo, useEffect, useState} from 'react';
import {DropdownMenu, DropdownMenuContent, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger} from '../ui/dropdown-menu';
import {Button} from '../ui/button';
import {Checkbox} from '../ui/checkbox';
import {Input} from '../ui/input';
import {useDialog} from '@/hooks/useDialog';
import {Dialog, DialogContent, DialogDescription, DialogPortal, DialogTitle, DialogTrigger} from '../ui/dialog';
import {twMerge} from 'tailwind-merge';
import {ListFilter, X} from 'lucide-react';

type Type = 'General' | 'GuidelineProposer' | 'MessageEventGenerator' | 'ToolCaller';
type Level = 'WARNING' | 'INFO' | 'DEBUG';
type Text = 'and' | 'or';

const ALL_TYPES: Type[] = ['General', 'GuidelineProposer', 'ToolCaller', 'MessageEventGenerator'];
const ALL_LEVELS: Level[] = ['WARNING', 'INFO', 'DEBUG'];
const TEXT_FILTERS: Text[] = ['and', 'or'];

const typeLabels: Record<Type, string> = {
	General: 'General',
	GuidelineProposer: 'Guideline Proposer',
	MessageEventGenerator: 'Message Event Composer',
	ToolCaller: 'Tool Caller',
};

const LogFilters = ({applyFn, def, filterId}: {applyFn: (types: string[], level: string, and: string[], or: string[]) => void; filterId?: number; def?: {level?: Level; types?: Type[]; and: string[]; or: string[]} | null}) => {
	const [sources, setSources] = useState(structuredClone(def?.types || []));
	const [andConditions, setAndConditions] = useState(structuredClone(def?.and || []));
	const [orConditions, setOrConditions] = useState(structuredClone(def?.or || []));
	const [level, setLevel] = useState<Level>(def?.level || ALL_LEVELS[ALL_LEVELS.length - 1]);
	const {openDialog, closeDialog, DialogComponent} = useDialog();

	useEffect(() => {
		if (filterId) {
			const types = structuredClone(def?.types || ALL_TYPES);
			const level = def?.level || ALL_LEVELS[ALL_LEVELS.length - 1];
			const and = def?.and || [];
			const or = def?.or || [];
			setSources(types);
			setLevel(level);
			setAndConditions(and);
			setOrConditions(or);
			applyFn(types, level, and, or);
		}
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [filterId]);

	useEffect(() => {
		setSources(def?.types || []);
		setLevel(def?.level || ALL_LEVELS[ALL_LEVELS.length - 1]);
	}, [def]);

	const changeSource = (type: Type, value: boolean, cb?: (sources: Type[], level: Level, and: string[], or: string[]) => void) => {
		setSources((val) => {
			if (value) val.push(type);
			else val = val.filter((item) => item !== type);
			const vals = [...new Set(val)];
			cb?.(vals, level, andConditions, orConditions);
			return vals;
		});
	};

	const TypeChip = ({type}: {type: Type}) => {
		return (
			<div key={type} className='group bg-[#EBECF0] h-[30px] flex items-center gap-[8px] pt-[6px] pb-[5px] ps-[14px] rounded-[5px] hover:bg-[#DDDEE2]'>
				<p className='text-nowrap font-normal text-[14px]'>{typeLabels[type]}</p>
				<X role='button' className='invisible pe-[12px] size-[28px] group-hover:visible' onClick={() => changeSource(type, false, applyFn)} />
			</div>
		);
	};

	const CondChip = memo(({text}: {text: string}) => {
		return (
			<div key={text} className='bg-white border-[#656565] border-[1px] h-[30px] rounded-[5px] flex justify-center items-center'>
				<div className='group flex items-center justify-center rounded-[3px] h-[calc(100%-4px)] w-[calc(100%-4px)] py-[5px] ps-[14px] gap-[8px] bg-white border border-[#CDCDCD]'>
					<p className='text-nowrap font-normal text-[14px]'>{text}</p>
					<X role='button' className='invisible me-[8px] size-[20px] group-hover:visible' />
					{/* <img
						src='icons/close-white.svg'
						alt='close'
						className='pe-[12px]'
						role='button'
						// onClick={() => {
						// 	changeSource(type, false);
						// 	applyFn(sources, level);
						// }}
					/> */}
				</div>
			</div>
		);
	});

	const DropDownFilter = () => {
		const [dropdownOpen, setDropdownOpen] = useState(false);
		const [sources, setSources] = useState<Type[]>(def?.types || []);

		const changeSource = (type: Type, value: boolean) => {
			setSources((val) => {
				if (value) val.push(type);
				else val = val.filter((item) => item !== type);
				const vals = [...new Set(val)];
				return vals;
			});
		};
		return (
			<DropdownMenu open={dropdownOpen} onOpenChange={setDropdownOpen}>
				<DropdownMenuTrigger asChild>
					{!def?.types?.length || dropdownOpen ? (
						<Button variant='outline' className='flex items-center gap-[6px] h-[30px] px-[14px] bg-white hover:bg-[#E1E2E6]'>
							<ListFilter className='[stroke-width:2px] size-[16px]' />
							{/* <img src='icons/filter.svg' alt='' /> */}
							<p className='text-[14px] font-medium'>Filters</p>
						</Button>
					) : (
						<Button variant='outline' className='flex bg-white hover:bg-[#E1E2E6] items-center gap-[6px] w-[32px] h-[30px] p-0'>
							<img src='icons/filter.svg' alt='' />
						</Button>
					)}
				</DropdownMenuTrigger>
				<DropdownMenuContent className='font-ubuntu-sans font-normal bg-white w-[218px]'>
					<DropdownMenuLabel className='flex items-center justify-between py-[2px]'>
						<p className='text-[15px] text-[#A9A9A9] font-normal'>Filter...</p>
						<img src='icons/close-white.svg' alt='close' role='button' onClick={() => setDropdownOpen(false)} />
					</DropdownMenuLabel>
					<DropdownMenuSeparator className='bg-[#EBECF0]' />
					<div className='flex flex-col gap-[4px] mt-[9px] pb-[11px] ps-[15px] pe-[21px]'>
						{ALL_TYPES.map((type) => (
							<div key={type} className={twMerge('flex items-center py-[4px] ps-[6px] space-x-2 hover:bg-[#F5F6F8]', sources.includes(type) && 'bg-[#EBECF0]')}>
								<Checkbox id={type} defaultChecked={def?.types?.includes(type)} className='border-black !bg-white' onCheckedChange={(isChecked) => changeSource(type, !!isChecked)} />
								<label className='text-[12px] font-normal w-full cursor-pointer' htmlFor={type}>
									{typeLabels[type]}
								</label>
							</div>
						))}
					</div>
					<DropdownMenuSeparator className='bg-[#EBECF0]' />
					<div className={'inputs flex flex-col gap-[6px] px-[21px] pb-[14px] pt-[11px]'}>
						{TEXT_FILTERS.map((text: 'and' | 'or') => (
							<Dialog key={text} aria-hidden={false}>
								<DialogTrigger>
									<div className='group border rounded-[3px] h-[22px] flex items-center bg-[#FBFBFB] hover:bg-[#F5F6F8]'>
										<p className='ps-[10px] text-[12px] capitalize'>{text}:</p>
										<Input onClick={() => dialogOpen(text)} className='h-[20px] !ring-0 !ring-offset-0 border-none text-[12px] bg-[#FBFBFB] hover:bg-[#F5F6F8]' />
									</div>
								</DialogTrigger>
								<DialogPortal aria-hidden={false}>
									<DialogContent className='p-0' aria-hidden={false}>
										<DialogTitle className='hidden'>Filter By Content</DialogTitle>
										<DialogDescription className='hidden'>Filter By Content</DialogDescription>
										<FilterDialogContent type={text} />
									</DialogContent>
								</DialogPortal>
							</Dialog>
						))}
					</div>
					<DropdownMenuSeparator className='bg-[#EBECF0]' />
					<div className='buttons flex items-center'>
						<Button onClick={() => applyFn([], 'DEBUG', [], [])} variant='ghost' className='flex-1 text-[12px] font-normal text-[#656565] h-[35px] w-[95px]'>
							Clear all
						</Button>
						<Button
							variant='ghost'
							onClick={() => {
								applyFn(sources, level, andConditions, orConditions);
								setDropdownOpen(false);
							}}
							className='flex-1 text-[12px] font-normal !text-white bg-blue-main h-[35px] w-[95px] hover:bg-[#1000EB]'>
							Apply
						</Button>
					</div>
				</DropdownMenuContent>
			</DropdownMenu>
		);
	};

	const FilterDialogContent = memo(({type}: {type: 'and' | 'or'}) => {
		const [inputVal, setInputVal] = useState('');
		const onApplyClick = () => {
			console.log(inputVal);
			applyFn(sources, level, type === 'and' ? [...andConditions, inputVal] : andConditions, type === 'or' ? [...orConditions, inputVal] : orConditions);
			closeDialog();
		};
		return (
			<div className='px-[40px] py-[42px] flex flex-col gap-[22px]'>
				<h2 className='text-[20px] font-normal'>Filter By Content</h2>
				<div className='border rounded-[5px] h-[38px] flex items-center bg-[#FBFBFB] hover:bg-[#F5F6F8] focus-within:!bg-white'>
					<p className='ps-[10px] text-[12px] text-[#151515] capitalize'>{type}:</p>
					<Input value={inputVal} onChange={(e) => setInputVal(e.target.value)} name='filter' className='h-[36px] !ring-0 !ring-offset-0 border-none text-[12px] bg-[#FBFBFB] hover:bg-[#F5F6F8] focus:!bg-white' />
				</div>
				<div className='buttons flex items-center gap-[24px] justify-end text-[16px] font-normal font-ubuntu-sans'>
					<Button variant='outline' onClick={closeDialog} className='h-[38px] w-[84px] !bg-white text-[#656565] hover:text-[#151515]'>
						Cancel
					</Button>
					<Button onClick={onApplyClick} className='bg-blue-main text-white h-[38px] w-[79px] hover:bg-[#1000EB]'>
						Apply
					</Button>
				</div>
			</div>
		);
	});

	const dialogOpen = (type: 'and' | 'or') => {
		openDialog(null, <FilterDialogContent type={type} />, {width: '580px', height: '236px'});
	};

	return (
		<div className='flex justify-between py-[10px] pe-[10px] ps-[24px] bg-white min-h-fit h-[70px]'>
			<div className='filters-button flex items-center gap-[8px] flex-wrap'>
				{!!def?.types?.length && def.types.map((type) => <TypeChip key={type} type={type} />)}
				{def?.and.map((and: string) => (
					<CondChip key={`And:${and}`} text={`And:${and}`} />
				))}
				{def?.or.map((or: string) => (
					<CondChip key={`Or:${or}`} text={`Or:${or}`} />
				))}
				<DropDownFilter />
			</div>
			<div className='flex gap-[20px]'>
				{/* <div>
					{types.map((type) => (
						<div key={type} className='flex items-center space-x-2'>
							<Checkbox id={type} defaultChecked={true} onCheckedChange={(isChecked) => changeSource(type, !!isChecked)} />
							<label htmlFor={type}>{type}</label>
						</div>
					))}
				</div> */}
				{/* <div>
					<RadioGroup defaultValue={level} onValueChange={(val) => setLevel(val)}>
						{ALL_LEVELS.map((l) => (
							<div key={l} className='flex items-center space-x-2'>
								<RadioGroupItem value={l} id={l} />
								<label htmlFor={l}>{l}</label>
							</div>
						))}
					</RadioGroup>
				</div> */}
			</div>
			{/* <Button className='self-end mb-[5px]' onClick={() => applyFn(sources, level)}>
				Apply
			</Button> */}
			<DialogComponent />
		</div>
	);
};

export default memo(LogFilters);
