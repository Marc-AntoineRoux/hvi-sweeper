-------------------------------------------------------------------------------
-- Brief : Top module for Quantum dot simulator	       
-- Module Name 	: Quantum_dot_simulator_Top
-- Author 		: Larissa Njejimana 
-- Institut quantique - Université de Sherbrooke
-- July 2020
-------------------------------------------------------------------------------

-------------------------------------------------------------------------------
--	Library and Package Declarations
-------------------------------------------------------------------------------
library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

Library UNISIM;
use UNISIM.VComponents.all;

-------------------------------------------------------------------------------
--	Entity Declaration
-------------------------------------------------------------------------------
entity Quantum_dot_simulator_Top is
Port ( 
	clk							: in std_logic;
	nrst						: in std_logic; -- logic low
	
	-- PC interface (PC_port or HVI_port)
    MEM_sdi_mem_S_address		: in std_logic_vector(9 downto 0);
    MEM_sdi_mem_S_wrEn			: in std_logic;
    MEM_sdi_mem_S_wrData		: in std_logic_vector(31 downto 0);
    MEM_sdi_mem_S_rdEn			: in std_logic;
    MEM_sdi_mem_S_rdData		: out std_logic_vector(31 downto 0);
    
    -- input voltages
    i_Vg1                       : in std_logic_vector(15 downto 0);
    i_Vg2                       : in std_logic_vector(15 downto 0);
    
    -- occupation 
    o_valid                     : out std_logic;
    o_occupation                : out std_logic_vector(15 downto 0)

);
end Quantum_dot_simulator_Top;

-------------------------------------------------------------------------------
--	Object declarations
-------------------------------------------------------------------------------
architecture Behavioral of Quantum_dot_simulator_Top is

    --	Components	
    component quantum_dot_simulator_0 is
    port (
        ap_clk          : in std_logic;                         -- clock : 100 MHz
        ap_rst          : in std_logic;                         -- reset : active high
        ap_start        : in std_logic;                         -- must be asserted to 1 for the design to begin operation and held until ap_ready = '1'
        ap_done         : out std_logic;                        -- Output set to 1 when operation complete. Indicates also when ap_return data is valid.
        ap_idle         : out std_logic;                        -- Output set to 1 when design is in idle state. Set to 0 once the design starts operating.
        ap_ready        : out std_logic;                        -- Output set to 1 when the design is ready to accept new inputs
        V1              : in std_logic_vector (15 downto 0);    -- Input voltage on Gate 1
        V2              : in std_logic_vector (15 downto 0);    -- Input voltage on Gate 2
        HVI_Cm          : in std_logic_vector (31 downto 0);    -- Capacitance between the 2 dots
        ap_return       : out std_logic_vector (15 downto 0)    -- Calculated occupation on (V1,V2) in function of Cm
    );
    end component;
    
    --	Convenient constants
 	constant c_zeros			: std_logic_vector(31 downto 0) := (others => '0');
 	constant c_ones 			: std_logic_vector(31 downto 0) := (0 =>'1', others => '0');
       
    --	User types and State Machines
    
    --	Signals	
    signal reset                : std_logic := '0';
    signal d_done               : std_logic := '0';
    signal d_ready              : std_logic := '0';
    signal d_idle               : std_logic := '0';
    signal d_occupation         : std_logic_vector(15 downto 0);
    
    --	Registers
    signal q_PCstartFlag        : std_logic := '0';
    signal q_start              : std_logic := '0';
    signal qq_start             : std_logic := '0';
    signal q_WaitingDone        : std_logic := '0';
    signal q_valid              : std_logic := '0';
    signal qq_valid              : std_logic := '0';
    signal q_occupation         : std_logic_vector(15 downto 0) := (others => '0');
    signal qq_occupation         : std_logic_vector(15 downto 0) := (others => '0');
    signal q_Vg1                : std_logic_vector(15 downto 0) := (others => '0');
    signal q_Vg2                : std_logic_vector(15 downto 0) := (others => '0');
    signal q_Cm                 : std_logic_vector(31 downto 0) := (others => '0');
    signal qq_Cm                : std_logic_vector(31 downto 0) := (others => '0');
    signal q_dataToPC	        : std_logic_vector(31 downto 0) := (others => '0');
    signal q_compteurCycles     : unsigned(31 downto 0) := (others => '0');
    signal q_compteurInterval   : unsigned(31 downto 0) := unsigned(c_ones); 
    
    
    -- Attributes
    attribute DONT_TOUCH : string;     -- avoid WARNING: [Synth 8-6014] bug in Vivado 2017.1 and later
    attribute DONT_TOUCH of  q_compteurCycles : signal is "TRUE";
    attribute DONT_TOUCH of  q_compteurInterval : signal is "TRUE";


---------------------------------------------------------------------------------------------
--	Behavior Section
---------------------------------------------------------------------------------------------
begin                          

    reset <= not nrst;
    
    Emulator: quantum_dot_simulator_0
    port map (
         ap_clk         => clk,    
         ap_rst         => reset, 
         ap_start       => q_start, 
         ap_done        => d_done, 
         ap_idle        => d_idle, 
         ap_ready       => d_ready, 
         
         V1             => q_Vg1, 
         V2             => q_Vg2,  
         HVI_Cm         => qq_Cm,
         
         ap_return      => d_occupation         
    ); 
    
    start: process(clk)
    begin
        if(clk'event and clk = '1') then
                    
            if(q_PCstartFlag = '1') then
                q_start    <= '1';
                q_WaitingDone <= '1';
                q_Vg1    <= i_Vg1;
                q_Vg2    <= i_Vg2;
            end if;
            
            if(d_ready = '1') then
                q_start <= '0';
            end if;    
            
            if(d_done = '1') then
                q_WaitingDone <= '0';
            end if;                      
        end if;
    end process; 
       
    outputs: process(clk)
    begin
        if(clk'event and clk = '1') then
            
            if(qq_start = '1') then
                q_valid <= '0'; 
            end if;
            
            if(d_done = '1') then
                q_occupation <= d_occupation; 
                q_valid <= '1';                       
            end if;            
        end if;
    end process;    
    
    Cm: process(clk)
    begin
        if(clk'event and clk = '1') then
            qq_Cm <= q_Cm;
            qq_start <= q_start;
            qq_occupation <= q_occupation;
            qq_valid <= q_valid;
        end if;
    end process;       
    
    compteur: process(clk)
    begin
        if(clk'event and clk = '1') then
            
            if(qq_start = '1') then
                q_compteurInterval <= q_compteurInterval + 1; 
            end if;     
                   
            if(q_WaitingDone = '1') then
                q_compteurCycles <= q_compteurCycles + 1; 
            end if;
            
            if(q_PCstartFlag = '1') then  
                q_compteurInterval <= unsigned(c_ones);                    
                q_compteurCycles <= unsigned(c_zeros);                    
            end if;
        end if;
    end process;
    
    FromPC: process(clk)
    begin
        if(clk'event and clk = '1') then
        
            q_PCstartFlag <= '0';
            
            if (MEM_sdi_mem_S_wrEn = '1') then            
                if (MEM_sdi_mem_S_address = "00" & X"00") then
                    q_PCstartFlag <= MEM_sdi_mem_S_wrData(0);
                    
                elsif(MEM_sdi_mem_S_address = "00" & X"08") then
                    q_Cm <= MEM_sdi_mem_S_wrData;
                end if;
                
            end if;
        end if;
    end process;    
    
    TowardPC: process(clk)
    begin
        if(clk'event and clk = '1') then
        
            if (MEM_sdi_mem_S_rdEn = '1') then
            
                 if (MEM_sdi_mem_S_address = "00" & X"00") then
                     q_dataToPC <= c_zeros(30 downto 0) & q_start;
                        
                elsif (MEM_sdi_mem_S_address = "00" & X"01") then
                     q_dataToPC <= c_zeros(15 downto 0) & q_occupation;
                        
                 elsif (MEM_sdi_mem_S_address = "00" & X"02") then
                     q_dataToPC <= c_zeros(15 downto 0) & i_Vg1;
                        
                 elsif (MEM_sdi_mem_S_address = "00" & X"03") then
                     q_dataToPC <= c_zeros(15 downto 0) & q_Vg1;   
                    
                 elsif (MEM_sdi_mem_S_address = "00" & X"04") then
                     q_dataToPC <= c_zeros(15 downto 0) & i_Vg2;
            
                 elsif (MEM_sdi_mem_S_address = "00" & X"05") then
                     q_dataToPC <= c_zeros(15 downto 0) & q_Vg2;
                        
                elsif (MEM_sdi_mem_S_address = "00" & X"06") then
                    q_dataToPC <= std_logic_vector(q_compteurCycles);  
                    
                elsif (MEM_sdi_mem_S_address = "00" & X"07") then
                    q_dataToPC <= std_logic_vector(q_compteurInterval); 
                    
                 elsif (MEM_sdi_mem_S_address = "00" & X"08") then
                     q_dataToPC <= q_Cm;               
                
                else
                    q_dataToPC <= c_zeros;
                    
                end if;   
            end if;
        end if;
    end process;

	---------------------------------------------------------------------------
	--				Outputs		
	---------------------------------------------------------------------------
    o_valid         		<= qq_valid;
    o_occupation    		<= qq_occupation;
	MEM_sdi_mem_S_rdData	<= q_dataToPC;
    
end Behavioral;
