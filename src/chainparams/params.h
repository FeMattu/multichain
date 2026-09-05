// Copyright (c) 2014-2019 Coin Sciences Ltd
// MultiChain code distributed under the GPLv3 license, see COPYING file.

#ifndef MULTICHAINPARAMS_H
#define	MULTICHAINPARAMS_H

#include "utils/declare.h"

#define MC_DEFAULT_NETWORK_PORT 8571
#define MC_DEFAULT_RPC_PORT 8570


#define MC_PRM_MAX_PARAM_NAME_SIZE       31
#define MC_PRM_MAX_ARG_NAME_SIZE         31
#define MC_PRM_PARAM_SIZE_BYTES           2
#define MC_PRM_MAX_DESCRIPTION_SIZE     255
#define MC_PRM_DECIMAL_GRANULARITY 1000000

#define MC_PRM_UNKNOWN          0x00000000
#define MC_PRM_BINARY           0x00000001
#define MC_PRM_STRING           0x00000002
#define MC_PRM_BOOLEAN          0x00000003
#define MC_PRM_INT32            0x00000004
#define MC_PRM_INT64            0x00000005
#define MC_PRM_DOUBLE           0x00000006
#define MC_PRM_UINT32           0x00000007
#define MC_PRM_DATA_TYPE_MASK   0x0000000F

#define MC_PRM_COMMENT          0x00000010
#define MC_PRM_USER             0x00000020
#define MC_PRM_GENERATED        0x00000030
#define MC_PRM_CALCULATED       0x00000040
#define MC_PRM_SOURCE_MASK      0x000000F0

#define MC_PRM_CLONE            0x00010000
#define MC_PRM_SPECIAL          0x00020000
#define MC_PRM_NOHASH           0x00040000
#define MC_PRM_MINIMAL          0x00080000
#define MC_PRM_DECIMAL          0x00100000
#define MC_PRM_HIDDEN           0x00200000
#define MC_PRM_TIME             0x00400000


#define MC_PRM_STATUS_EMPTY              0
#define MC_PRM_STATUS_MINIMAL            1
#define MC_PRM_STATUS_ERROR              2
#define MC_PRM_STATUS_GENERATED          3
#define MC_PRM_STATUS_INVALID            4
#define MC_PRM_STATUS_VALID              5

#define MC_PSK_APPLIED                   0
#define MC_PSK_INTERNAL_ERROR            1
#define MC_PSK_NOT_FOUND                 2
#define MC_PSK_WRONG_SIZE                3
#define MC_PSK_OUT_OF_RANGE              4
#define MC_PSK_FRESH_UPGRADE             5
#define MC_PSK_DOUBLE_RANGE              6
#define MC_PSK_NOT_SUPPORTED             7
#define MC_PSK_NEW_NOT_DOWNGRADABLE      8
#define MC_PSK_OLD_NOT_DOWNGRADABLE      9




extern int MCP_MAX_STD_OP_RETURN_COUNT;
extern int64_t MCP_INITIAL_BLOCK_REWARD;
extern int64_t MCP_FIRST_BLOCK_REWARD;
extern int MCP_TARGET_BLOCK_TIME;
extern int MAX_CHUNK_SIZE; 
extern int MAX_CHUNK_COUNT; 
extern int MAX_NBITS_FOR_SIGNED_NONCE; 
extern uint32_t MIN_CHUNK_SALT_SIZE;
extern uint32_t MAX_CHUNK_SALT_SIZE;
extern int MCP_ANYONE_CAN_ADMIN;
extern int MCP_ANYONE_CAN_MINE;
extern int MCP_ANYONE_CAN_CONNECT;
extern int MCP_ANYONE_CAN_SEND;
extern int MCP_ANYONE_CAN_RECEIVE;
extern int MCP_ANYONE_CAN_CREATE;
extern int MCP_ANYONE_CAN_ISSUE;
extern int MCP_ANYONE_CAN_ACTIVATE;
extern int64_t MCP_MINIMUM_PER_OUTPUT;
extern int MCP_ALLOW_ARBITRARY_OUTPUTS;
extern int MCP_ALLOW_MULTISIG_OUTPUTS;
extern int MCP_ALLOW_P2SH_OUTPUTS;
extern int MCP_WITH_NATIVE_CURRENCY;
extern int MCP_STD_OP_DROP_COUNT;
extern int MCP_STD_OP_DROP_SIZE;
extern int MCP_ANYONE_CAN_RECEIVE_EMPTY;

typedef struct mc_OneMultichainParam
{    
    char m_Name[MC_PRM_MAX_ARG_NAME_SIZE+1]; 
    char m_DisplayName[MC_PRM_MAX_ARG_NAME_SIZE+1]; 
    int m_Type;
    int m_MaxStringSize;
    int64_t m_DefaultIntegerValue;
    int64_t m_MinIntegerValue;
    int64_t m_MaxIntegerValue;
    double m_DefaultDoubleValue;
    int m_ProtocolVersion;
    int m_Removed;
    char m_ArgName[MC_PRM_MAX_PARAM_NAME_SIZE+1]; 
    char m_Next[MC_PRM_MAX_ARG_NAME_SIZE+1]; 
    char m_Group[MC_PRM_MAX_DESCRIPTION_SIZE+1]; 
    char m_Description[MC_PRM_MAX_DESCRIPTION_SIZE+1]; 
    
    int IsRelevant(int version);
} mc_OneMultichainParam;

typedef struct mc_MultichainParams
{    
    char *m_lpData;
    mc_MapStringIndex *m_lpIndex;
    mc_OneMultichainParam *m_lpParams;
    int *m_lpCoord;
    int m_Status;
    int m_Size;
    int m_Count;
    int m_IsProtocolMultiChain;
    int m_ProtocolVersion;
    int m_RelevantProtocolVersion;
    
    int m_AssetRefSize;
    
    mc_MultichainParams()
    {
        Zero();
    }

    ~mc_MultichainParams()
    {
        Destroy();
    }
    
    void Zero();                                                                // Initializes parameters set object
    void Init();                                                                // Initializes parameters set object
    void Destroy();                                                             // Destroys parameters set object
    
    int Create(const char *name,int version);
    int Read(const char *name);    
    int Read(const char* name,int argc, char* argv[],int create_version);
    int Clone(const char *name,mc_MultichainParams *source);
    int Build(const unsigned char* pubkey,int pubkey_size);

/* MCHN START - wPoA/weight-engine bootstrap ordering

   Raises setup-first-blocks to the floor the weight engine needs, when the chain is
   configured to run it under wPoA selection.

   wPoA starts electing proposers at setup-first-blocks, but the engine cannot compute the
   first weight until the first epoch is BURIED, at
       weight-epoch-length + MC_WEIGHT_DEFAULT_STABILITY_MARGIN - 1,
   and the value must then be published and CONFIRMED before the selector can read it --
   hence MC_WEIGHT_SETUP_PUBLISH_MARGIN on top.
   Set setup-first-blocks below that and a clean network has an empty weights registry exactly
   when the selector first needs one: nobody is elected, nobody mines, no epoch ever buries,
   and the chain stops dead at setup-first-blocks. The stock defaults (epoch 100, margin 6,
   setup 60) are on the wrong side of it.

   So the floor is DERIVED rather than merely checked: a smaller configured value is raised
   to it, a larger one is left alone (an operator may legitimately want a longer native setup
   phase). Callers report the change; *lpNewValue is 0 when nothing was touched.

   The two switches are passed IN, not read from params.dat: at genesis they may be arriving
   as runtime flags the file does not carry yet, and that is precisely the configuration that
   stalls.

   Only ever called while the chain is being CREATED — from Build(), before the parameter
   hash is computed, and from multichain-util. That is deliberate: setup-first-blocks is
   hash-enforced and inherited through params.dat, so the corrected value has to be part of
   the chain's identity from the start. It reaches every joining node by the normal
   parameter inheritance, and it is never rewritten on an existing chain, which would fork
   it. Cfr. §5.12.3 and the weight-engine epoch geometry. */

    int AdjustSetupFirstBlocks(int weight_engine_on,int wpoa_selection_on,
                               int64_t *lpOldValue,int64_t *lpNewValue);
/* MCHN END */

    int Validate();
    int CalculateHash(unsigned char *hash);
    int Write(int overwrite);
    int Print(FILE *);
    int SetGlobals();
    int SetProtocolGlobals();
    int SetUpgradedParamValue(const mc_OneMultichainParam *param,int64_t value);
    int Import(const char *name,const char *source_address);
    int Set(const char *name,const char *source,int source_size);
    
    const mc_OneMultichainParam *FindParam(const char *param);
    void* GetParam(const char *param,int* size);
    int64_t GetInt64Param(const char *param);
    double GetDoubleParam(const char *param);
    double Int64ToDecimal(int64_t value);
    int64_t DecimalToInt64(double value);
    int GetParamFromScript(char* ptr,int64_t *value,int *size);
    
    int SetParam(const char *param,const char* value,int size);
    int SetParam(const char *param,int64_t value);
    
    int CanBeUpgradedByVersion(const char *param,int version,int size);
    int IsParamUpgradeValueInRange(const mc_OneMultichainParam *param,int version,int64_t value);
    
    const char* Name();
    const unsigned char* DefaultMessageStart();
    const unsigned char* MessageStart();
    const unsigned char* AddressVersion();
    const unsigned char* AddressCheckumValue();
    const unsigned char* AddressScriptVersion();
    int ProtocolVersion();
    int IsProtocolMultichain();
    double ParamAccuracy();
    

    
} mc_MultichainParams;


#endif	/* MULTICHAINPARAMS_H */

