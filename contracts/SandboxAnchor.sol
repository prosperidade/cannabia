// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title SandboxAnchor
 * @notice Registra raizes Merkle de eventos operacionais da plataforma
 *         CannabIA no ambito do Sandbox Regulatorio da ANVISA (RDC
 *         1.014/2026), fornecendo prova publica de ancoragem com
 *         carimbo temporal on-chain.
 *
 * @dev    Contrato append-only por design — nao expoe setters nem
 *         delete. Cada chamada a ``anchor`` adiciona uma linha
 *         imutavel. Qualquer verificador (ANVISA, auditor, imprensa)
 *         pode cruzar o merkleRoot deste contrato com o valor em
 *         ``blockchain_anchors.merkle_root`` da CannabIA e com a
 *         Merkle proof devolvida pelo endpoint publico
 *         ``GET /api/v1/public/anchors/<tenant>/verify`` (F5.5).
 *
 *         Deploy inicial: Polygon Amoy (testnet) para homologacao
 *         regulatoria. Promocao para Polygon mainnet apos validacao
 *         formal com a autoridade e consultoria juridica.
 *
 *         Escopo (doc 26 §4.1-4.3):
 *           - 'global': ancoragem agregada de multiplos tenants/projects.
 *           - 'tenant': ancoragem por associacao.
 *           - 'project': ancoragem vinculada a Projeto Experimental.
 *
 *         Custo esperado: centavos a poucos reais por submissao,
 *         confirmacao em ~2-3 minutos (10 blocos Polygon).
 */
contract SandboxAnchor {
    // ---------------------------------------------------------------
    // Storage
    // ---------------------------------------------------------------

    /// @dev Metadata minima por ancoragem. merkleRoot e o dado-chave;
    ///      os demais campos fornecem contexto para verificacao e
    ///      analytics off-chain.
    struct Anchor {
        string scope;        // 'global' | 'tenant' | 'project'
        bytes32 scopeId;     // 0x00..00 para 'global'; keccak256 ou big-endian id caso contrario
        bytes32 merkleRoot;  // raiz Merkle dos eventos cobertos
        uint64 periodStart;  // unix timestamp (UTC) — inicio da janela coberta
        uint64 periodEnd;    // unix timestamp (UTC) — fim da janela
        address submitter;   // msg.sender
        uint64 anchoredAt;   // block.timestamp no momento da ancoragem
    }

    /// @dev Array de ancoragens. Index e o anchorId publico.
    Anchor[] public anchors;

    // ---------------------------------------------------------------
    // Events
    // ---------------------------------------------------------------

    /**
     * @notice Emitido a cada nova ancoragem. Os 3 campos indexed
     *         permitem filtros eficientes: por anchorId, por scopeId
     *         (tenant/project especifico) ou por merkleRoot.
     */
    event Anchored(
        uint256 indexed anchorId,
        bytes32 indexed scopeId,
        bytes32 indexed merkleRoot,
        string scope,
        uint64 periodStart,
        uint64 periodEnd,
        address submitter,
        uint64 anchoredAt
    );

    // ---------------------------------------------------------------
    // Write
    // ---------------------------------------------------------------

    /**
     * @notice Registra uma nova ancoragem.
     * @param scope "global" | "tenant" | "project"
     * @param scopeId 32 bytes que identificam escopo (0 para global)
     * @param merkleRoot raiz Merkle (nao-zero)
     * @param periodStart unix timestamp do inicio da janela
     * @param periodEnd unix timestamp do fim da janela (>= periodStart)
     * @return anchorId index da ancoragem no array ``anchors``
     *
     * @dev Validacoes defensivas em cadeia — a camada off-chain ja
     *      valida, mas on-chain previne submissoes invalidas que
     *      entrariam no historico.
     */
    function anchor(
        string calldata scope,
        bytes32 scopeId,
        bytes32 merkleRoot,
        uint64 periodStart,
        uint64 periodEnd
    ) external returns (uint256 anchorId) {
        require(merkleRoot != bytes32(0), "SandboxAnchor: merkleRoot=0");
        require(periodEnd >= periodStart, "SandboxAnchor: invalid period");
        require(
            keccak256(bytes(scope)) == keccak256("global") ||
            keccak256(bytes(scope)) == keccak256("tenant") ||
            keccak256(bytes(scope)) == keccak256("project"),
            "SandboxAnchor: invalid scope"
        );

        uint64 nowTs = uint64(block.timestamp);
        anchorId = anchors.length;
        anchors.push(Anchor({
            scope: scope,
            scopeId: scopeId,
            merkleRoot: merkleRoot,
            periodStart: periodStart,
            periodEnd: periodEnd,
            submitter: msg.sender,
            anchoredAt: nowTs
        }));

        emit Anchored(
            anchorId, scopeId, merkleRoot,
            scope, periodStart, periodEnd,
            msg.sender, nowTs
        );
    }

    // ---------------------------------------------------------------
    // Read / verify
    // ---------------------------------------------------------------

    function anchorsCount() external view returns (uint256) {
        return anchors.length;
    }

    /**
     * @notice Retorna todos os campos de uma ancoragem.
     * @param anchorId id devolvido por ``anchor()``
     */
    function getAnchor(uint256 anchorId)
        external
        view
        returns (Anchor memory)
    {
        require(anchorId < anchors.length, "SandboxAnchor: out of bounds");
        return anchors[anchorId];
    }

    /**
     * @notice Verifica se uma raiz Merkle informada bate com a
     *         ancoragem identificada por ``anchorId``. Composto com
     *         a Merkle proof off-chain, permite prova de inclusao de
     *         evento individual na ancoragem.
     */
    function verifyRoot(
        uint256 anchorId,
        bytes32 merkleRoot
    ) external view returns (bool) {
        if (anchorId >= anchors.length) {
            return false;
        }
        return anchors[anchorId].merkleRoot == merkleRoot;
    }
}
